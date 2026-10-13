import os, uuid, subprocess
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template
from openai import OpenAI
app=Flask(__name__)
BASE=Path(__file__).resolve().parent
TMP=BASE/"tmp"; OUT=BASE/"outputs"
TMP.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
app.config["MAX_CONTENT_LENGTH"]=300*1024*1024
@app.get("/")
def home(): return render_template("index.html")
@app.get("/health")
def health(): return jsonify(status="ok")
def ffmpeg(*args):
 p=subprocess.run(["ffmpeg","-y",*args],capture_output=True,text=True)
 if p.returncode: raise RuntimeError("Video processing failed. Try a shorter video.")
@app.post("/api/dub")
def dub():
 key=os.getenv("OPENAI_API_KEY")
 if not key: return jsonify(error="Site owner must configure OPENAI_API_KEY in hosting settings."),503
 video=request.files.get("video"); target=request.form.get("target_language","Urdu")
 if not video or not video.filename: return jsonify(error="Please upload a video."),400
 job=uuid.uuid4().hex; src=TMP/f"{job}.mp4"; wav=TMP/f"{job}.wav"; mp3=TMP/f"{job}.mp3"; out=OUT/f"{job}_dubbed.mp4"
 video.save(src)
 try:
  ffmpeg("-i",str(src),"-vn","-ac","1","-ar","16000",str(wav))
  client=OpenAI(api_key=key)
  with wav.open("rb") as a: transcript=client.audio.transcriptions.create(model="gpt-4o-mini-transcribe",file=a).text.strip()
  if not transcript: return jsonify(error="No speech detected."),400
  translated=client.responses.create(model="gpt-4o-mini",input=f"Translate this spoken dialogue into {target}. Return only the translation:\n{transcript}").output_text.strip()
  client.audio.speech.create(model="gpt-4o-mini-tts",voice="coral",input=translated,response_format="mp3").write_to_file(mp3)
  ffmpeg("-i",str(src),"-i",str(mp3),"-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-shortest",str(out))
  return jsonify(download=f"/download/{job}",target=target)
 except Exception as e:
  app.logger.exception("Dubbing failed"); return jsonify(error=str(e)[:400]),500
 finally:
  for p in (src,wav,mp3):
   try: p.unlink(missing_ok=True)
   except OSError: pass
@app.get("/download/<job>")
def download(job):
 p=OUT/f"{job}_dubbed.mp4"
 return send_file(p,as_attachment=True,download_name="DubAI_dubbed.mp4") if p.is_file() else ("Not found",404)
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.getenv("PORT","8000")))
