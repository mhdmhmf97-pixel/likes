from flask import Flask, request, jsonify
import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import time
import threading

app = Flask(__name__)
last_sent_cache = {}
lock = threading.Lock()

# ------------------- تشفير -------------------
def Encrypt_ID(x):
    x = int(x)
    dec = ['80','81','82','83','84','85','86','87','88','89','8a','8b','8c','8d','8e','8f','90','91','92','93','94','95','96','97','98','99','9a','9b','9c','9d','9e','9f','a0','a1','a2','a3','a4','a5','a6','a7','a8','a9','aa','ab','ac','ad','ae','af','b0','b1','b2','b3','b4','b5','b6','b7','b8','b9','ba','bb','bc','bd','be','bf','c0','c1','c2','c3','c4','c5','c6','c7','c8','c9','ca','cb','cc','cd','ce','cf','d0','d1','d2','d3','d4','d5','d6','d7','d8','d9','da','db','dc','dd','de','df','e0','e1','e2','e3','e4','e5','e6','e7','e8','e9','ea','eb','ec','ed','ee','ef','f0','f1','f2','f3','f4','f5','f6','f7','f8','f9','fa','fb','fc','fd','fe','ff']
    xxx = ['1','01','02','03','04','05','06','07','08','09','0a','0b','0c','0d','0e','0f','10','11','12','13','14','15','16','17','18','19','1a','1b','1c','1d','1e','1f','20','21','22','23','24','25','26','27','28','29','2a','2b','2c','2d','2e','2f','30','31','32','33','34','35','36','37','38','39','3a','3b','3c','3d','3e','3f','40','41','42','43','44','45','46','47','48','49','4a','4b','4c','4d','4e','4f','50','51','52','53','54','55','56','57','58','59','5a','5b','5c','5d','5e','5f','60','61','62','63','64','65','66','67','68','69','6a','6b','6c','6d','6e','6f','70','71','72','73','74','75','76','77','78','79','7a','7b','7c','7d','7e','7f']
    x = x / 128
    if x > 128:
        x = x / 128
        if x > 128:
            x = x / 128
            if x > 128:
                x = x / 128
                strx = int(x)
                y = (x - int(strx)) * 128
                z = (y - int(y)) * 128
                n = (z - int(z)) * 128
                m = (n - int(n)) * 128
                return dec[int(m)] + dec[int(n)] + dec[int(z)] + dec[int(y)] + xxx[int(x)]
            else:
                strx = int(x)
                y = (x - int(strx)) * 128
                z = (y - int(y)) * 128
                n = (z - int(z)) * 128
                return dec[int(n)] + dec[int(z)] + dec[int(y)] + xxx[int(x)]

def encrypt_api(plain_text):
    plain_text = bytes.fromhex(plain_text)
    key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
    iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    cipher_text = cipher.encrypt(pad(plain_text, AES.block_size))
    return cipher_text.hex()

# ------------------- إرسال لايك -------------------
def send_like_request(token, TARGET):
    url = "https://clientbp.ggblueshark.com/LikeProfile"
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)',
        'Connection': 'Keep-Alive',
        'Expect': '100-continue',
        'X-Unity-Version': '2018.4.11f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB50',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Bearer {token}'
    }
    try:
        resp = httpx.post(url, headers=headers, data=TARGET, verify=False, timeout=10)
        if "invalid" in resp.text.lower():
            return {"token": token[:20]+"...", "status_code": 401, "response_text": "invalid signature"}
        return {
            "token": token[:20]+"...",
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "response_text": resp.text
        }
    except Exception as e:
        return {
            "token": token[:20]+"...",
            "status_code": "error",
            "headers": {},
            "response_text": str(e)
        }

# ------------------- API Flask -------------------
@app.route("/send_like", methods=["GET"])
def send_like():
    player_id = request.args.get("player_id")
    if not player_id:
        return jsonify({"error": "player_id is required"}), 400
    try:
        player_id_int = int(player_id)
    except ValueError:
        return jsonify({"error": "player_id must be an integer"}), 400

    now = time.time()
    last_sent = last_sent_cache.get(player_id_int, 0)
    if now - last_sent < 86400:
        return jsonify({"error": "Likes already sent within last 24 hours",
                        "seconds_until_next_allowed": int(86400 - (now - last_sent))}), 429

    # جلب معلومات اللاعب
    try:
        info_url = f"https://info-theta-azure.vercel.app/get?uid={player_id}"
        resp = httpx.get(info_url, timeout=10)
        info_json = resp.json()
        account_info = info_json.get("AccountInfo", {})
        player_name = account_info.get("AccountName","Unknown")
        player_uid = account_info.get("accountId",player_id_int)
        likes_before = account_info.get("AccountLikes",0)
    except Exception as e:
        return jsonify({"error": f"Error fetching player info: {e}"}), 500

    encrypted_id = Encrypt_ID(player_uid)
    encrypted_api_data = encrypt_api(f"08{encrypted_id}1007")
    TARGET = bytes.fromhex(encrypted_api_data)

    likes_sent = 0
    results = []
    failed = []
    max_likes = 100

    # ✅ جلب كل التوكنات مرة واحدة فقط
    try:
        token_data = httpx.get("https://aauto-token.onrender.com/api/get_jwt", timeout=50).json()
        tokens_dict = token_data.get("tokens", {})
        token_items = list(tokens_dict.items())
        random.shuffle(token_items)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch tokens: {e}"}), 500

    # ✅ كل توكن يُستخدم مرة واحدة فقط
    with ThreadPoolExecutor(max_workers=200) as executor:
        futures = {executor.submit(send_like_request, token, TARGET): (uid, token)
                   for uid, token in token_items}
        for future in as_completed(futures):
            uid, token = futures[future]
            res = future.result()
            if res["status_code"] == 200:
                with lock:
                    if likes_sent < max_likes:
                        likes_sent += 1
                        results.append(res)
            else:
                failed.append(res)

    last_sent_cache[player_id_int] = now
    likes_after = likes_before + likes_sent

    return jsonify({
        "player_id": player_uid,
        "player_name": player_name,
        "likes_before": likes_before,
        "likes_added": likes_sent,
        "likes_after": likes_after,
        "seconds_until_next_allowed": 86400,
        "success_tokens": results,
        "failed_tokens": failed
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
