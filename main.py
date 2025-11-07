import os
import json
import base64
import time
import requests
from dotenv import load_dotenv
load_dotenv()
MONDAY_API_KEY  = os.getenv("MONDAY_API_KEY")
BOARD_ID        = os.getenv("MONDAY_BOARD_ID", "4189846836")
WORKIOM_WEBHOOK = os.getenv("WORKIOM_WEBHOOK")
IMGBB_API_KEY   = os.getenv("IMGBB_API_KEY")
GOFILE_API_KEY  = os.getenv("GOFILE_API_KEY")
# ================================
# MONDAY'DEN ITEM ÇEKME
# ================================
def get_monday_items():
   # BURAYI GEREKİRSE GÜNCELLE: files yerine dosya sütununun ID’sini yaz
   query = f"""
   query {{
     boards (ids: {BOARD_ID}) {{
       items {{
         id
         name
         column_values(ids: ["files"]) {{
           value
         }}
       }}
     }}
   }}
   """
   headers = {"Authorization": MONDAY_API_KEY, "Content-Type": "application/json"}
   res = requests.post("https://api.monday.com/v2", json={"query": query}, headers=headers)
   data = res.json()
   if "errors" in data:
       print("❌ Monday API hatası:", data["errors"])
       return []
   items = data.get("data", {}).get("boards", [{}])[0].get("items", [])
   print(f"✅ Monday'den {len(items)} item bulundu.")
   return items
# ================================
# DOSYALARI İNDİRME
# ================================
def download_files(file_value):
   try:
       file_info = json.loads(file_value or "null")
   except json.JSONDecodeError:
       return []
   if not file_info or not file_info.get("files"):
       return []
   downloaded = []
   seen_assets = set()
   for file_obj in file_info["files"]:
       asset_id = str(file_obj.get("assetId") or "")
       if asset_id in seen_assets:
           continue
       seen_assets.add(asset_id)
       file_url = file_obj.get("url") or file_obj.get("public_url")
       if not file_url and asset_id:
           query = f"query {{ assets (ids: [{asset_id}]) {{ public_url }} }}"
           headers = {"Authorization": MONDAY_API_KEY, "Content-Type": "application/json"}
           res = requests.post("https://api.monday.com/v2", json={"query": query}, headers=headers)
           data = res.json()
           file_url = data.get("data", {}).get("assets", [{}])[0].get("public_url")
       if not file_url:
           continue
       filename = file_obj.get("name", f"file_{asset_id}.bin")
       try:
           r = requests.get(file_url, timeout=120)
           r.raise_for_status()
           with open(filename, "wb") as f:
               f.write(r.content)
           print(f"📥 indirildi: {filename}")
           downloaded.append(filename)
       except Exception as e:
           print(f"❌ indirme hatası {filename}: {e}")
   return downloaded
# ================================
# IMGBB YÜKLEME (görseller)
# ================================
def upload_imgbb(path):
   try:
       with open(path, "rb") as f:
           encoded = base64.b64encode(f.read())
       data = {"key": IMGBB_API_KEY, "image": encoded}
       r = requests.post("https://api.imgbb.com/1/upload", data=data, timeout=60)
       res = r.json()
       link = (res.get("data") or {}).get("url")
       if link:
           print(f"✅ imgbb linki: {link}")
       else:
           print(f"⚠️ imgbb hata: {res}")
       return link
   except Exception as e:
       print(f"❌ imgbb yükleme hatası: {e}")
       return None
# ================================
# GOFILE YÜKLEME (diğer dosyalar)
# ================================
def upload_gofile(path):
   try:
       s = requests.get("https://api.gofile.io/servers", timeout=10).json()["data"]["servers"][0]["name"]
       with open(path, "rb") as f:
           r = requests.post(
               f"https://{s}.gofile.io/uploadFile",
               files={"file": f},
               data={"token": GOFILE_API_KEY},
               timeout=600,
           )
       data = r.json()
       if data["status"] == "ok":
           link = data["data"]["downloadPage"]
           print(f"✅ GoFile linki: {link}")
           return link
       else:
           print(f"⚠️ GoFile hata: {data}")
           return None
   except Exception as e:
       print(f"❌ GoFile yükleme hatası: {e}")
       return None
# ================================
# WORKIOM'A GÖNDER
# ================================
def send_to_workiom(title, links):
   if not links:
       print(f"⚠️ {title} için link yok, gönderim atlandı.")
       return
   payload = {"title": title, "files": links}
   headers = {"Content-Type": "application/json"}
   res = requests.post(WORKIOM_WEBHOOK, json=payload, headers=headers, timeout=30)
   print(f"📤 {title} gönderildi ({res.status_code})")
# ================================
# ANA AKIŞ
# ================================
def main():
   items = get_monday_items()
   for it in items:
       name = it["name"]
       val = it["column_values"][0]["value"]
       if not val:
           continue
       print(f"\n📌 İşleniyor: {name}")
       downloaded = download_files(val)
       if not downloaded:
           continue
       links = []
       for f in downloaded:
           ext = os.path.splitext(f)[1].lower()
           if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
               link = upload_imgbb(f)
           else:
               link = upload_gofile(f)
           if link:
               links.append(link)
           os.remove(f)
       send_to_workiom(name, links)
       time.sleep(0.5)
if __name__ == "__main__":
   main()

