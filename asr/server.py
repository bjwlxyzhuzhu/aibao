"""本地语音识别服务：SenseVoice-Small（FunASR）+ FSMN-VAD 切分长音频。音频不出园。"""
import os
import tempfile

from fastapi import FastAPI, File, UploadFile

app = FastAPI(title="aibao-asr")
_model = None


def model():
    global _model
    if _model is None:
        from funasr import AutoModel
        _model = AutoModel(model=os.getenv("ASR_MODEL", "iic/SenseVoiceSmall"), vad_model="fsmn-vad",
                           vad_kwargs={"max_single_segment_time": 30000}, device="cpu", disable_update=True)
    return _model


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    from funasr.utils.postprocess_utils import rich_transcription_postprocess
    suffix = os.path.splitext(file.filename or "a.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as f:
        f.write(await file.read())
        f.flush()
        res = model().generate(input=f.name, language="zh", use_itn=True, batch_size_s=60, merge_vad=True)
    text = "".join(rich_transcription_postprocess(r["text"]) for r in res)
    return {"text": text}


@app.get("/health")
def health():
    return {"ok": True}
