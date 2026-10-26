"""Isolated trainer process. Imported GPU libraries never enter the platform venv."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import traceback
from uuid import UUID


class Stopped(RuntimeError):
    pass


def main(argv=None):
    # -I ignores PYTHONIOENCODING. Set the owned log streams before importing
    # trainer dependencies, whose multilingual progress messages can exceed CP950.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    run_id = str(UUID(args.run_id))
    sys.path.insert(0, str(root))
    from backend import compute_lease, training_environment as environment
    from backend.training_files import digest, file_manifest, read_json, verify_files, step_budget

    target = root / 'runtime/training/runs' / run_id
    manifest = read_json(target / 'manifest.json')
    if digest(target / 'manifest.json') != args.manifest_sha256 or manifest['run_id'] != run_id:
        raise ValueError('The frozen run manifest differs from the controller request.')
    config = manifest['configuration']
    offset, remaining_steps = step_budget(manifest)
    state = read_json(target / 'state.json')
    torch = None
    lease = None
    samples, done = [], threading.Event()
    monitor = None

    def update(status, **extra):
        state.update(
            status=status,
            updated_at=datetime.now(timezone.utc).isoformat(),
            pid=os.getpid(),
            **extra,
        )
        compute_lease.atomic_json(target / 'state.json', state)

    def engine_alive():
        with socket.socket() as connection:
            connection.settimeout(0.3)
            return connection.connect_ex(('127.0.0.1', 8188)) == 0

    def cancellation():
        if (target / 'stop.request').exists():
            raise Stopped('Stop requested for this run.')
        if engine_alive():
            raise Stopped('Managed ComfyUI started during training; this run was stopped.')

    def nvidia(fields, *, processes=False):
        query = '--query-compute-apps=' if processes else '--query-gpu='
        result = subprocess.run(
            [
                'nvidia-smi',
                '--id=' + str(config['gpu_index']),
                query + fields,
                '--format=csv,noheader,nounits',
            ],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        if result.returncode:
            raise ValueError('NVIDIA device observation is unavailable.')
        return result.stdout.strip()

    def sample():
        import psutil

        process = psutil.Process()
        while not done.is_set() and len(samples) < 3600:
            row = dict(
                elapsed_seconds=round(time.monotonic() - started, 3),
                rss_bytes=None,
                process_peak_working_set_bytes=None,
                whole_gpu_used_bytes=None,
            )
            try:
                memory = process.memory_info()
                row['rss_bytes'] = memory.rss
                row['process_peak_working_set_bytes'] = getattr(memory, 'peak_wset', None)
            except (OSError, psutil.Error):
                pass
            try:
                row['whole_gpu_used_bytes'] = int(nvidia('memory.used').splitlines()[0]) * 1024**2
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
            samples.append(row)
            done.wait(1)

    started = time.monotonic()
    exit_code = 1
    try:
        update('starting')
        lease = compute_lease.Reservation(root, 'training', run_id)
        lease.__enter__()
        if engine_alive():
            raise compute_lease.ComputeBusy(
                'Managed ComfyUI 8188 is running. Finish its jobs and stop it before training.'
            )
        cancellation()
        env = environment.check(root)
        if not env['ready'] or any(
            env[key] != manifest['environment'][key]
            for key in ('profile_sha256', 'dependencies_sha256', 'trainer_revision')
        ):
            raise ValueError('The verified training environment changed.')
        verify_files(target / 'work', manifest['frozen_files'])
        if list((target / 'output').iterdir()):
            raise ValueError('Training output is not empty; existing results were not overwritten.')
        if (
            digest(manifest['base']['path']) != manifest['base']['sha256']
            or Path(manifest['base']['path']).stat().st_size != manifest['base']['size_bytes']
        ):
            raise ValueError('The pinned base checkpoint changed.')
        if manifest['resume']:
            verify_files(target / 'resume', manifest['resume']['files'])
        for line in nvidia('pid,process_name', processes=True).splitlines():
            pid, _, name = line.partition(',')
            if int(pid.strip()) != os.getpid() and Path(name.strip()).name.lower() in (
                'python.exe',
                'pythonw.exe',
                'python',
                'python3',
            ):
                raise compute_lease.ComputeBusy(
                    'Another Python GPU process is active; finish its work before training.'
                )
        device_observation = nvidia('uuid,name,memory.total,memory.free')
        monitor = threading.Thread(target=sample, daemon=True)
        monitor.start()
        cancellation()
        sys.path.insert(0, str(environment.locations(root)['source']))
        import torch as torch_module

        torch = torch_module
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise ValueError('The selected CUDA training device is unavailable.')
        torch.cuda.reset_peak_memory_stats()
        import accelerate
        import sdxl_train_network
        from library import args as args_util

        save_state = accelerate.Accelerator.save_state

        def sealed_save(accelerator, output_dir=None, *arguments, **options):
            result = save_state(accelerator, output_dir, *arguments, **options)
            folder = Path(output_dir).resolve()
            if folder.parent != (target / 'output').resolve() or not folder.name.startswith(
                'model-'
            ):
                raise ValueError('Trainer attempted to save state outside this run.')
            train_state = read_json(folder / 'train_state.json')
            step = train_state['current_step'] + offset
            train_state['current_step'] = step
            compute_lease.atomic_json(folder / 'train_state.json', train_state)
            receipt = dict(
                schema_version=1,
                run_id=run_id,
                step=step,
                directory=folder.name,
                manifest_sha256=args.manifest_sha256,
                files=file_manifest(folder),
            )
            compute_lease.atomic_json(target / 'checkpoints' / f'step-{step}.json', receipt)
            update('running', last_checkpoint_step=step)
            return result

        accelerate.Accelerator.save_state = sealed_save

        class Trainer(sdxl_train_network.SdxlNetworkTrainer):
            def on_step_start(self, *arguments, **options):
                cancellation()
                return super().on_step_start(*arguments, **options)

            def _save_model(self, **options):
                options['steps'] += offset
                result = super()._save_model(**options)
                update('running', steps_completed=options['steps'])
                return result

        arguments = [
            '--pretrained_model_name_or_path',
            manifest['base']['path'],
            '--dataset_config',
            str(target / 'work/dataset.toml'),
            '--output_dir',
            str(target / 'output'),
            '--output_name',
            'model',
            '--save_model_as',
            'safetensors',
            '--network_module',
            'networks.lora',
            '--network_train_unet_only',
            '--network_dim',
            str(config['rank']),
            '--network_alpha',
            str(config['rank']),
            '--learning_rate',
            str(config['learning_rate']),
            '--max_train_steps',
            str(remaining_steps),
            '--save_every_n_steps',
            str(config['save_every_steps']),
            '--seed',
            str(config['seed']),
            '--mixed_precision',
            'fp16',
            '--save_precision',
            'fp16',
            '--optimizer_type',
            'AdamW',
            '--lr_scheduler',
            'constant',
            '--sdpa',
            '--gradient_checkpointing',
            '--cache_latents',
            '--cache_latents_to_disk',
            '--cache_text_encoder_outputs',
            '--cache_text_encoder_outputs_to_disk',
            '--max_data_loader_n_workers',
            '0',
            '--save_state',
            '--save_state_on_train_end',
            '--tokenizer_cache_dir',
            str(environment.locations(root)['tokenizers']),
        ]
        if manifest['resume']:
            # Upstream otherwise resets global_step while skipping epochs. Load
            # all accelerator state, explicitly train only the remaining budget,
            # and translate saved steps back to the frozen run's global budget.
            arguments += ['--resume', str(target / 'resume'), '--initial_step', '0']
        compute_lease.atomic_json(target / 'trainer-arguments.json', dict(arguments=arguments))
        training_args = sdxl_train_network.setup_parser().parse_args(arguments)
        args_util.verify_command_line_training_args(training_args)
        training_args = args_util.read_config_from_file(
            training_args, sdxl_train_network.setup_parser()
        )
        update(
            'running',
            device_observation=device_observation,
            torch_version=torch.__version__,
            cuda_runtime=torch.version.cuda,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        Trainer().train(training_args)
        if (
            read_json(target / 'output/model-state/train_state.json')['current_step']
            != config['max_steps']
        ):
            raise ValueError('Final saved state did not reach the frozen step budget.')
        outputs = {
            path.name: dict(size_bytes=path.stat().st_size, sha256=digest(path))
            for path in (target / 'output').glob('*.safetensors')
        }
        if 'model.safetensors' not in outputs:
            raise ValueError('Trainer returned without the final safetensors artifact.')
        compute_lease.atomic_json(
            target / 'artifacts.json',
            dict(
                schema_version=1,
                run_id=run_id,
                manifest_sha256=args.manifest_sha256,
                files=outputs,
                technical_only=config['purpose'] == 'technical-smoke',
            ),
        )
        update(
            'completed',
            steps_completed=config['max_steps'],
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        exit_code = 0
    except Stopped as exc:
        update('stopped', message=str(exc), finished_at=datetime.now(timezone.utc).isoformat())
        exit_code = 2
    except compute_lease.ComputeBusy as exc:
        update('blocked', message=str(exc), finished_at=datetime.now(timezone.utc).isoformat())
        exit_code = 3
    except BaseException as exc:
        update(
            'failed',
            message=str(exc)[:2000],
            error_type=type(exc).__name__,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        traceback.print_exc()
    finally:
        done.set()
        if monitor is not None:
            monitor.join(timeout=6)
        metrics = dict(
            elapsed_seconds=round(time.monotonic() - started, 3),
            samples=samples,
            torch_peak_allocated_bytes=None,
            torch_peak_reserved_bytes=None,
            gpu_measurement='whole-device observed values; other applications may contribute',
            allocator_measurement='training-process PyTorch allocator high-water marks',
        )
        if torch is not None and torch.cuda.is_initialized():
            metrics.update(
                torch_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                torch_peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            )
        compute_lease.atomic_json(target / 'resources.json', metrics)
        # No explicit lease release: process teardown releases both CUDA and the
        # OS lock, even if the controlling CLI has been interrupted or exited.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)


if __name__ == '__main__':
    main()
