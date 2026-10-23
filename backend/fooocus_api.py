from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from backend import fooocus_workflows as flow


def install(app, host, submissions):
    class Input(host.InpaintFeatherInput):
        inpaint_model: Literal['fooocus-v2.6']
        denoise: float = Field(default=1, strict=True, ge=1, le=1)

        @model_validator(mode='after')
        def supported(self):
            if self.checkpoint != flow.BASE['filename'] or self.loras:
                raise ValueError('專用修補只支援固定 Animagine 4.0 Opt，首版不組合 LoRA')
            return self

    host.FooocusInput = Input

    class Generate(Input):
        request_id: UUID

    @app.get('/api/fooocus-inpaint/workflow')
    def description():
        return dict(
            id=flow.ID,
            implemented=True,
            architectures=['sdxl'],
            checkpoint=flow.BASE['filename'],
            denoise=1,
            lora=False,
            policy=flow.policy(),
        )

    @app.post('/api/fooocus-inpaint/generate')
    async def generate(value: Generate):
        return await submissions.submit(value, flow)
