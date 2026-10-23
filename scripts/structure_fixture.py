"""Synthetic schemas for isolated browser tests, never real GPU evidence."""

F = lambda lo, hi: ['FLOAT', dict(min=lo, max=hi)]
STRUCTURE_NODES = {
    'ControlNetLoader': dict(
        input=dict(required=dict(control_net_name=[['pose.safetensors', 'depth.safetensors']])),
        output=['CONTROL_NET'],
    ),
    'ControlNetApplyAdvanced': dict(
        input=dict(
            required=dict(
                positive=['CONDITIONING'],
                negative=['CONDITIONING'],
                control_net=['CONTROL_NET'],
                image=['IMAGE'],
                strength=F(0, 10),
                start_percent=F(0, 1),
                end_percent=F(0, 1),
            ),
            optional=dict(vae=['VAE']),
        ),
        output=['CONDITIONING', 'CONDITIONING'],
    ),
    'DWPreprocessor': dict(
        input=dict(
            required=dict(
                image=['IMAGE'],
                detect_hand=[['enable', 'disable']],
                detect_body=[['enable', 'disable']],
                detect_face=[['enable', 'disable']],
                resolution=['INT', dict(min=64, max=8192)],
                bbox_detector=[['yolox_l.onnx']],
                pose_estimator=[['dw-ll_ucoco_384.onnx']],
                scale_stick_for_xinsr_cn=[['enable', 'disable']],
            )
        ),
        output=['IMAGE', 'POSE_KEYPOINT'],
    ),
    'DepthAnythingV2Preprocessor': dict(
        input=dict(
            required=dict(
                image=['IMAGE'],
                ckpt_name=[['depth_anything_v2_vits.pth']],
                resolution=['INT', dict(min=64, max=8192)],
            )
        ),
        output=['IMAGE'],
    ),
    'ImageScale': dict(
        input=dict(
            required=dict(
                image=['IMAGE'],
                upscale_method=[['bicubic']],
                width=['INT', dict(min=1, max=8192)],
                height=['INT', dict(min=1, max=8192)],
                crop=[['disabled']],
            )
        ),
        output=['IMAGE'],
    ),
}
