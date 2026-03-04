from fastapi import FastAPI, Form, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from moviepy.editor import ImageClip, concatenate_videoclips, TextClip, CompositeVideoClip, AudioFileClip
from moviepy.video.fx.all import fadein, fadeout
from PIL import Image
import os
import shutil
import tempfile
import uuid
from gtts import gTTS

app = FastAPI()
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads"
VIDEO_DIR = "videos"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/generate")
async def generate(
    description: str = Form(...),
    phone: str = Form(default=""),
    images: list[UploadFile] = File(...)
):
    if not images:
        raise HTTPException(400, "Trebuie cel puțin o poză!")
    if not description.strip():
        raise HTTPException(400, "Descriere obligatorie!")

    photo_paths = []
    for img in images:
        if not img.content_type.startswith("image/"):
            continue
        path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{img.filename}")
        with open(path, "wb") as f:
            shutil.copyfileobj(img.file, f)
        photo_paths.append(path)

    if not photo_paths:
        raise HTTPException(400, "Nicio poză validă!")

    audio_path = None
    try:
        full_text = description.strip()
        if phone.strip():
            full_text += f"\n\nPentru detalii sunați la {phone.strip()}."

        # Generare audio gTTS (gratuit, română)
        tts = gTTS(text=full_text, lang='ro', slow=False)
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        audio_path = tmp.name
        tmp.close()
        tts.save(audio_path)

        audio_clip = AudioFileClip(audio_path)
        audio_dur = audio_clip.duration

        num = len(photo_paths)
        total_dur = max(num * 4.0, audio_dur) + 5
        total_dur = min(240, max(10, total_dur))
        per_photo = total_dur / max(1, num)

        clips = []
        tmp_imgs = []
        for i, p in enumerate(photo_paths):
            img = Image.open(p).resize((1280, 720), Image.LANCZOS)
            tmp_img = os.path.join(UPLOAD_DIR, f"res_{uuid.uuid4()}.jpg")
            img.save(tmp_img)
            tmp_imgs.append(tmp_img)

            clip = ImageClip(tmp_img).set_duration(per_photo).fx(fadein, 1).fx(fadeout, 1)

            txt = ""
            if i == 0:
                txt = description[:100] + "..." if len(description) > 100 else description
            if i == num - 1 and phone.strip():
                txt = f"Contact: {phone.strip()}\nApel acum!"

            if txt:
                txt_clip = (
                    TextClip(txt, fontsize=48, color='white', stroke_color='black',
                             stroke_width=2, font='Arial-Bold', method='caption',
                             size=(clip.w - 100, None))
                    .set_position(('center', 'bottom'))
                    .set_duration(per_photo)
                )
                clip = CompositeVideoClip([clip, txt_clip])

            clips.append(clip)

        video = concatenate_videoclips(clips, method="compose").set_audio(audio_clip)
        out_file = os.path.join(VIDEO_DIR, f"vid_{uuid.uuid4().hex[:8]}.mp4")
        video.write_videofile(out_file, fps=24, codec='libx264', audio_codec='aac', threads=2)

        # Cleanup
        os.remove(audio_path)
        for p in photo_paths + tmp_imgs:
            if os.path.exists(p):
                os.remove(p)

        return FileResponse(out_file, filename="videoclip_publicitar.mp4", media_type="video/mp4")

    except Exception as e:
        for p in photo_paths:
            if os.path.exists(p):
                os.remove(p)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        raise HTTPException(500, str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
