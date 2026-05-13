import os
import re
import requests
from urllib.parse import urlparse

# 保存目录
SAVE_DIR = "xian_incident_materials"
os.makedirs(SAVE_DIR, exist_ok=True)

# 你要下载的资料链接，自己往这里加
URLS = [
    "https://www.xasb.net/",
    "https://www.chnmuseum.cn/zp/zpml/gmww/202112/t20211207_252694.shtml",
    "https://www.ncha.gov.cn/art/2021/2/2/art_1027_165676.html",
    "https://cpc.people.com.cn/GB/33837/2534330.html",
    "https://www.nopss.gov.cn/GB/219567/219576/16263953.html",
    "https://pdfyl.ertongbook.com/27/31317006.pdf",
    "https://lishiwenhua.snnu.edu.cn/__local/A/D1/B3/4B65D635D7CE9CABEF4CD7FB3ED_7CFB22FB_4FFA2.pdf?e=.pdf",
    "https://www.krzzjn.com/uploadfile/2020/0506/20200506092300334.pdf",
    "https://ivantsoi.myds.me/web/schoolebook/pdf/067041.pdf",
    "https://www.haodangke.com/soppt/287224-1.html",
    "https://wenku.baidu.com/view/2f50ffdd2f3f5727a5e9856a561252d380eb20a9.html",
    "https://www.openclass.chc.edu.tw/storage/47/111/%E8%AA%B2%E7%A8%8B%E8%B3%87%E6%96%99.pdf/H62eMovb7r81koIDeGK8oEB57h7p9dSw5NmQYuhy.pdf",
    "https://dangshi.people.com.cn/n1/2021/0902/c437524-32215781.html",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def safe_filename(name: str) -> str:
    name = re.sub(r'[\\\\/:*?"<>|]+', "_", name)
    return name[:150]

def guess_filename(url: str, response: requests.Response) -> str:
    # 先看响应头
    content_type = response.headers.get("Content-Type", "").lower()

    # 从 URL 取文件名
    path = urlparse(url).path
    basename = os.path.basename(path)

    if basename:
        filename = safe_filename(basename)
    else:
        filename = "index.html"

    # 如果没有扩展名，根据类型补
    if "." not in filename:
        if "pdf" in content_type:
            filename += ".pdf"
        elif "html" in content_type:
            filename += ".html"
        else:
            filename += ".bin"

    return filename

def download_file(url: str):
    try:
        print(f"正在下载: {url}")
        with requests.get(url, headers=HEADERS, timeout=30, stream=True) as r:
            r.raise_for_status()
            filename = guess_filename(url, r)
            filepath = os.path.join(SAVE_DIR, filename)

            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        print(f"已保存: {filepath}\n")

    except requests.RequestException as e:
        print(f"下载失败: {url}")
        print(f"原因: {e}\n")

if __name__ == "__main__":
    for url in URLS:
        download_file(url)

    print("全部任务结束。")