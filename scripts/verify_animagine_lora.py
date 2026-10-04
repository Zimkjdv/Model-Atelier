"""Fixed Animagine + LCM SDXL single-LoRA acceptance, independent of Pony evidence."""
from scripts import verify_animagine_generation as animagine, verify_lora_generation as lcm


def settings(engine, checkpoint):
    return animagine.settings(engine, checkpoint) | dict(
        title='Animagine + LCM single LoRA GPU acceptance', steps=4, cfg=1.0,
        sampler_name='lcm', scheduler='sgm_uniform',
        loras=[dict(name=lcm.LORA['filename'], enabled=True, strength_model=1.0, strength_clip=0.0)])


class AnimagineLoraAcceptance(lcm.LoraAcceptance):
    checkpoint_manifest = animagine.MODEL

    def expected_settings(self):
        return settings(self.engine, self.checkpoint)


def main(argv=None):
    return lcm.base.main(argv, runner_type=AnimagineLoraAcceptance,
                         default_report='runtime/animagine-lcm-acceptance.json',
                         default_checkpoint=animagine.MODEL['filename'])


if __name__ == '__main__':
    raise SystemExit(main())
