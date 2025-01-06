from flask import Flask, redirect, render_template, request, send_file, jsonify, send_from_directory, url_for, session
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_mail import Mail, Message
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from urllib import request as urllib_rq
from urllib.parse import urlencode
from bs4 import BeautifulSoup
import concurrent.futures
from datetime import timedelta
from time import sleep
import threading, io, os, re, random, logging, cloudscraper, string, pyotp


app = Flask(__name__)

app.secret_key = os.urandom(24)
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=3)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT'))
mail_username = os.environ.get('MAIL_USERNAME')
app.config['MAIL_USERNAME'] = mail_username
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS') == 'True'
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL') == 'True'
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')
otp_secret = os.environ.get('OTP_SECRET')

totp = pyotp.TOTP(otp_secret)
mail = Mail(app)
jwt = JWTManager(app)

VALID_USERS = {
    os.environ.get("USER_NAME"): os.environ.get("USER_PASSWORD")
}


logging.basicConfig(level=logging.INFO)

logger = logging.getLogger('LoggingTest')
sh = logging.StreamHandler()
logger.addHandler(sh)
logger.setLevel(logging.INFO)


progress_store = {}
novel_store = {}
background_tasks = {}
lock = threading.Lock()

def get_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def get_random_user_agent():
    windows_versions = ["10.0"]
    chrome_versions = f"{random.randint(119,129)}.0.0.0"
    user_agent = (
        f"Mozilla/5.0 (Windows NT {random.choice(windows_versions)}; Win64; x64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{chrome_versions} Safari/537.36"
    )
    return user_agent

def get_random_referer():
    referers = [
        "https://www.google.com/search?q=%E3%83%8F%E3%83%BC%E3%83%A1%E3%83%AB%E3%83%B3&ie=UTF-8&oe=UTF-8&hl=ja-jp&client=safari",
        "https://syosetu.org/",
        "https://syosetu.org/search/?mode=search",
        "https://syosetu.org/?mode=rank",
        "https://syosetu.org/?mode=favo"
    ]
    return random.choice(referers)
    
def get_narou_random_referer():
    referers = [
        "https://www.google.com/search?q=%E5%B0%8F%E8%AA%AC%E5%AE%B6%E3%81%AB%E3%81%AA%E3%82%8D%E3%81%86&ie=utf-8&oe=utf-8",
        "https://www.google.com/search?q=%E5%B0%8F%E8%AA%AC%E3%82%92%E8%AA%AD%E3%82%82%E3%81%86&ie=utf-8&oe=utf-8",
        "https://syosetu.com/user/top/",
        "https://syosetu.com/favnovelmain/list/?nowcategory=2&order=newlist",
        "https://yomou.syosetu.com/search.php",
        "https://yomou.syosetu.com/rank/top/"
    ]
    return random.choice(referers)

def get_random_delay():
    return random.uniform(2, 8)

def get_chapter_text(scraper, url, headers, nid, wasuu, retry_count=3):
    for _ in range(retry_count):
        try:
            sleep(get_random_delay())
            response = scraper.get(url, headers=headers,cookies={'ETURAN': f'{nid}_{wasuu}', 'over18':'off'})
            soup = BeautifulSoup(response.text, "html.parser")
            chapter_title_tags = soup.find(id='maind')
            if chapter_title_tags.find('span', class_='alert_color'):
                chapter_title_tag = chapter_title_tags.find_all('span')[2]
            else:
                chapter_title_tag = chapter_title_tags.find_all('span')[1]
            chapter_title_text = chapter_title_tag.decode_contents()
            for tag in ['ruby', 'rb', 'rt', 'rp']:
                chapter_title_text = chapter_title_text.replace(f'<{tag}>', '').replace(f'</{tag}>', '')
            result = [str(part).strip() for part in chapter_title_text.split('<br/>') if part.strip()]
            chapter_title = (
                f'# {result[0]}\n## {result[1]}\n\n' if len(result) == 2 else 
                f'## {result[0]}\n\n' if len(result) == 1 else 
                ''
            )
            chapter_text = '\n'.join(p.text for p in soup.find(id='honbun').find_all('p'))
            return chapter_title + chapter_text
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}. Retrying...")
            sleep(get_random_delay())
    return ""


def get_novel_txt(novel_url: str, nid: str):
    novel_url = novel_url.rstrip('/') + '/'
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ja-JP,ja;q=0.9",
        "Referer": get_random_referer(),
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive"
    }
    
    scraper = cloudscraper.create_scraper()

    try:
        sleep(get_random_delay())
        response = scraper.get(novel_url, headers=headers, cookies={'over18':'off'})
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.find('div', class_='ss').find('span', attrs={'itemprop':'name'}).text
        chapter_count = len(soup.select('a[href^="./"]'))

        txt_data = [None] * chapter_count

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_to_url = {executor.submit(get_chapter_text, scraper, f'{novel_url}{i+1}.html', headers, nid, i+1): i for i in range(chapter_count)}
            completed_chapters = 0
            for future in concurrent.futures.as_completed(future_to_url):
                chapter_num = future_to_url[future]
                try:
                    chapter_text = future.result()
                    txt_data[chapter_num] = chapter_text
                    completed_chapters += 1
                    progress_store[nid] = [int((completed_chapters / chapter_count) * 100), title]
                except Exception as exc:
                    print(f'Chapter {chapter_num} generated an exception: {exc}')

        novel_text = '\n\n'.join(filter(None, txt_data))
        novel_store[nid] = [novel_text, title]
        progress_store[nid] = [100, title]

    except Exception as e:
        print(f"Error fetching novel: {str(e)}")

def get_narou_chapter_text(scraper, url, headers, nid, wasuu, retry_count=3):
    for _ in range(retry_count):
        try:
            sleep(get_random_delay())
            response = scraper.get(url, headers=headers,cookies={'ETURAN': f'{nid}_{wasuu}', 'over18':'off'})
            soup = BeautifulSoup(response.text, "html.parser")
            chapter_title_tags = soup.find(id='maind')
            if chapter_title_tags.find('span', class_='alert_color'):
                chapter_title_tag = chapter_title_tags.find_all('span')[2]
            else:
                chapter_title_tag = chapter_title_tags.find_all('span')[1]
            chapter_title_text = chapter_title_tag.decode_contents()
            for tag in ['ruby', 'rb', 'rt', 'rp']:
                chapter_title_text = chapter_title_text.replace(f'<{tag}>', '').replace(f'</{tag}>', '')
            result = [str(part).strip() for part in chapter_title_text.split('<br/>') if part.strip()]
            chapter_title = (
                f'# {result[0]}\n## {result[1]}\n\n' if len(result) == 2 else 
                f'## {result[0]}\n\n' if len(result) == 1 else 
                ''
            )
            chapter_text = '\n'.join(p.text for p in soup.find(id='honbun').find_all('p'))
            return chapter_title + chapter_text
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}. Retrying...")
            sleep(get_random_delay())
    return ""

def get_narou_novel_txt(novel_url: str, ncode: str):
    novel_url = novel_url.rstrip('/') + '/'
    ks2 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    cookie = {'over18':'yes', 'ks2':ks2, 'sasieno':'0'}
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ja-JP,ja;q=0.9",
        "Referer": get_narou_random_referer(),
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive"
    }
    
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome','platform': 'windows','desktop': True})
    
    try:
        sleep(get_random_delay())
        if 'ncode' in novel_url:
            novel_info_url = f'https://ncode.syosetu.com/novelview/infotop/ncode/{ncode}/'
            response = urllib_rq.urlopen(novel_info_url, headers=headers, cookies=cookie)
            #response = scraper.get(novel_info_url, headers=headers, cookies=cookie)
        elif 'novel18' in novel_url:
            novel_info_url = f'https://novel18.syosetu.com/novelview/infotop/ncode/{ncode}/'
            response = scraper.get(novel_info_url, headers=headers, cookies=cookie)
        
        print(f'response.status_code: {response.status_code}')
        print(f'response.headers: {response.headers}')
        print(f'response.text: {response.text[:500]}')
        
        
        sleep(get_random_delay())
        response = scraper.get(novel_url, headers=headers, cookies=cookie)
        print('Response text:', response.text[:500])
        soup = BeautifulSoup(response.text, "html.parser")
        print('soup: ', soup.prettify())
        
        """
        chapter_count = len(soup.select('a[href^="./"]'))

        txt_data = [None] * chapter_count

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_to_url = {executor.submit(get_narou_chapter_text, scraper, f'{novel_url}{i+1}.html', headers, nid, i+1): i for i in range(chapter_count)}
            completed_chapters = 0
            for future in concurrent.futures.as_completed(future_to_url):
                chapter_num = future_to_url[future]
                try:
                    chapter_text = future.result()
                    txt_data[chapter_num] = chapter_text
                    completed_chapters += 1
                    progress_store[nid] = [int((completed_chapters / chapter_count) * 100) - 1, title]
                except Exception as exc:
                    print(f'Chapter {chapter_num} generated an exception: {exc}')

        novel_text = '\n\n'.join(filter(None, txt_data))
        novel_store[nid] = [novel_text, title]
        progress_store[nid] = [100, title]
        """
    except Exception as e:
        print(f"Error fetching novel: {str(e)}")

def start_scraping_task(url, nid, site):
    current_thread = threading.current_thread()
    with lock:
        if nid in background_tasks and background_tasks[nid] is not current_thread and background_tasks[nid].is_alive():
            return
    if site == 'syosetu_org':
        get_novel_txt(url, nid)
    elif site == 'ncode_syosetu_com':
        get_narou_novel_txt(url, nid)
    with lock:
        background_tasks.pop(nid, None)

def parse_novel(novel):
    title = novel.find('a').text
    link = novel.find('a').get('href')
    author_info = novel.find_all('div', class_='blo_title_sak')[-1].text.split('\n')
    author = author_info[2][2:]
    parody = author_info[1].replace('原作：','').replace('オリジナル：','')
    description = novel.find('div', class_='blo_inword').text
    status = novel.find('div', class_='blo_wasuu_base').find('span').text
    latest = novel.find('a', attrs={'title':'最新話へのリンク'}).text
    updated_day = novel.find('div', attrs={'title':'最終更新日'}).text
    words = novel.find('div', attrs={'title': '総文字数'}).text.split(' ')[1]
    evaluation = novel.find('div', class_='blo_hyouka').text.strip()[5:]
    all_keywords = novel.find('div', class_='all_keyword').find_all('a')
    alert_keywords = [x.text for x in novel.find('div', class_='all_keyword').find('span').find_all('a')]
    keywords = [x.text for x in all_keywords if x.text not in alert_keywords]
    favs = novel.find_all('div', attrs={'style': 'background-color: transparent;'})[-1].text.split('｜')[1][6:]

    return {
        'title': title,
        'link': link,
        'author': author,
        'parody': parody,
        'description': description,
        'status': status,
        'latest': latest,
        'updated_day': f'{updated_day[:10]} {updated_day[10:]}',
        'words': words,
        'evaluation': evaluation,
        'alert_keywords': alert_keywords,
        'keywords': keywords,
        'favs': favs
    }

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        username = data.get("username")
        password = data.get("password")
        if username in VALID_USERS and password == VALID_USERS[username]:
            otp_code = totp.now()
            msg = Message('Your OTP Code', recipients=[mail_username])
            msg.body = f'ワンタイムパスワード︰ {otp_code}'
            mail.send(msg)
            session['mail_username'] = mail_username
            return jsonify({"message": "OTP has been sent to your email."}), 200
        return jsonify({"error": "Authentication failed."}), 401
    return render_template('login.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        data = request.json
        otp_code = data.get("otp_code")
        if 'mail_username' in session and totp.verify(otp_code):
            access_token = create_access_token(identity=session['mail_username'])
            session.pop('mail_username', None)
            return jsonify(access_token=access_token), 200
        return jsonify({"error": "Invalid OTP code."}), 401
    return render_template('verify.html')

@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200

@app.route('/', methods=['GET', 'POST'])
@jwt_required(optional=True)
def index():
    current_user = get_jwt_identity()
    return render_template('index.html', user=current_user)

@app.route('/start-scraping', methods=['POST'])
def start_scraping():
    url = request.json['url']
    match_syosetu = re.search(r'https://syosetu.org/novel/(\d+)/', url)
    match_ncode = re.search(r'https://ncode.syosetu.com/([a-z0-9]+)/', url)
    
    if match_syosetu:
        nid = match_syosetu.group(1)
        novel_url = f"https://syosetu.org/novel/{nid}/"
        site = 'syosetu_org'
    elif match_ncode:
        nid = match_ncode.group(1)
        novel_url = f"https://ncode.syosetu.com/{nid}/"
        site = 'ncode_syosetu_com'
    else:
        return jsonify({"error": "Invalid URL format. Please enter a valid URL."}), 400
    
    with lock:
        if nid in background_tasks and background_tasks[nid].is_alive():
            return jsonify({"status": "in_progress", "nid": nid})

        try:
            task = threading.Thread(target=start_scraping_task, args=(novel_url, nid, site))
            task.start()
            background_tasks[nid] = task
            progress_store[nid] = [0, ""]
            return jsonify({"status": "started", "nid": nid})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

@app.route('/progress/<nid>', methods=['GET'])
def get_progress(nid):
    progress = progress_store.get(nid, [-1])[0]
    title = progress_store.get(nid, ['',''])[1]
    return jsonify({"progress": progress, "title": title})

@app.route('/download/<nid>', methods=['GET'])
def download_novel(nid):
    novel = novel_store[nid]
    if novel:
        buffer = io.BytesIO()
        buffer.write(novel[0].encode('utf-8'))
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f'{novel[1]}.txt', mimetype='text/plain')
    else:
        return jsonify({"error": "Novel not found or scraping not completed"}), 404

@app.route('/search', methods=['POST'])
def search():
    word = request.form.get('word', '')
    checkedR18 = request.form.get('mode', 'search')
    parody = request.form.get('parody', '')
    type_value = request.form.get('type', '0')

    filter_params = ['rensai_s1', 'rensai_s2', 'rensai_s4', 'mozi2', 'mozi1', 'mozi2_all', 'mozi1_all', 'rate2', 'rate1', 
                     'soupt2', 'soupt1', 'f2', 'f1', 're2', 're1', 'v2', 'v1', 
                     'r2', 'r1', 't2', 't1', 'd2', 'd1']

    url_params = {
        'mode': checkedR18,
        'word': word,
        'gensaku': parody,
        'type': type_value
    }

    for param in filter_params:
        value = request.form.get(param)
        if value:
            url_params[param] = value

    base_url = "https://syosetu.org/search/"
    url = f"{base_url}?{urlencode(url_params)}"

    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ja-JP,ja;q=0.9",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1"
    }
    scraper = cloudscraper.create_scraper()
    #with get_session() as session:
    try:
        sleep(random.uniform(2,4))
        response = scraper.get(url, headers=headers, cookies={'over18':'off', 'list_num':'50'})
        soup = BeautifulSoup(response.text, 'html.parser')
        novels = soup.find_all('div', class_='section3')

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_index = {executor.submit(parse_novel, novel): i for i, novel in enumerate(novels)}
            results = [None] * len(novels)
                
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                results[index] = future.result()

        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('static', 'service-worker.js')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('static', 'sitemap.xml')

if __name__ == '__main__':
    app.run(debug=False)