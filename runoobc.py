import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse

downloaded_files = {}
depth = 0


def is_valid_url_or_relative_path(url):
    if not url:
        exit("空url，什么玩意")
    # 尝试解析URL
    try:
        result = urlparse(url)
        # 如果URL没有scheme（即不是完整的URL），但包含路径（至少一个/），则可能是相对路径
        if not result.scheme and result.path:
            return True
        # 如果有scheme，则至少需要一个netloc
        elif result.scheme and result.netloc:
            return True
    except ValueError:
        # 如果解析失败，则URL不合法
        return False

    # 如果以上条件都不满足，则返回False
    return False


def remove_trailing_slash(s):
    if s.endswith('/'):
        return s[:-1]
    else:
        return s


def inspect():
    print("##################")
    for key, value in downloaded_files.items():
        print(key)
    print("####################")


def remove_query_from_url(url_2):
    # 使用 urlparse 解析 URL
    parsed_url = urlparse(url_2)

    # 创建一个新的 URL 元组，省略 query 部分
    # 注意：需要将 query 替换为空字符串 ''
    new_url_parts = (parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, '', parsed_url.fragment)

    # 使用 urlunparse 重新组合 URL
    new_url = urlunparse(new_url_parts)

    return new_url


def download_src(soup, output_dir, base_url):
    for tag in soup.find_all(True, src=True):
        src_attr = tag['src']
        if not is_valid_url_or_relative_path(src_attr):
            continue
        if src_attr.startswith('data:'):
            continue  # 忽略Base64编码的图片

        abs_url = urljoin(base_url, src_attr)
        parsed_url = urlparse(abs_url)
        filename = os.path.basename(remove_trailing_slash(parsed_url.path))
        local_path = os.path.join(output_dir, filename)
        print("深度" + str(depth) + ":处理src=" + abs_url + "中...", end='')
        if not filename:
            continue
        # 如果文件尚未下载，则下载并保存
        if local_path not in downloaded_files:
            try:
                response = requests.get(abs_url, stream=True)
            except:
                downloaded_files[local_path] = True
                continue

            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

                downloaded_files[local_path] = True

        # 4. 替换src属性
        tag['src'] = os.path.relpath(local_path, output_dir)  # 使用相对路径或绝对路径，根据你的需要选择
        print("完毕")


def download_css_href(soup, output_dir, base_url):
    for tag in soup.find_all('link', rel='stylesheet'):
        href_attr = tag['href']
        if not is_valid_url_or_relative_path(href_attr):
            continue
        abs_url = urljoin(base_url, href_attr)
        parsed_url = urlparse(abs_url)
        filename = os.path.basename(remove_trailing_slash(parsed_url.path))
        local_path = os.path.join(output_dir, filename)
        print("深度" + str(depth) + ":处理css,href=" + abs_url + "中...", end='')
        if local_path not in downloaded_files:
            try:
                response = requests.get(abs_url, stream=True)
            except:
                print("css加载失败")
                continue
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            downloaded_files[local_path] = True

        tag['href'] = os.path.relpath(local_path, output_dir)
        print("完毕")


#######
def download_and_replace_recursion(url, output_dir, base_url):
    global url_a
    global set_depth
    # 1. 下载网页内容
    global depth
    depth += 1
    # 设置递归深度，太多太慢也没用
    try:
        response = requests.get(url)
    except:
        print('子站链接失败')
        depth -= 1
        return
    # response.raise_for_status()
    html_content = response.text

    # 2. 解析HTML内容
    soup = BeautifulSoup(html_content, 'html.parser')
    # 3. 下载并保存资源
    download_src(soup, output_dir, base_url)
    # 前一个for循环结束，接下来的for循环用来捕捉css的外部样式的href
    download_css_href(soup, output_dir, base_url)

    for tag in soup.find_all('a', href=True):
        href_attr = tag['href']
        if not is_valid_url_or_relative_path(href_attr):
            continue
        abs_url = urljoin(base_url, href_attr)
        parsed_url = urlparse(abs_url)
        filename = os.path.basename(remove_trailing_slash(parsed_url.path))
        local_path = os.path.join(output_dir, filename)
        print("深度" + str(depth) + ":开始处理子页面url=" + abs_url + "中...", end='')
        if not parsed_url.netloc == urlparse(url_a).netloc:
            print("跳过(广告或者js代码)")
            continue
        if not filename:
            print("跳过(主页面)")
            continue
        if local_path not in downloaded_files and depth <= set_depth:
            print(f"\n深度{depth}->{depth + 1}::深入递归")
            download_and_replace_recursion(abs_url, output_dir, remove_query_from_url(abs_url))
            print(f"深度{depth + 1}->{depth}::递归完毕")
        else:
            print("已经加载完毕")
        tag['href'] = os.path.relpath(local_path, output_dir)
    print(f"深度{depth}:递归完毕,开始写入当前页面...", end='')
    # 5. 保存修改后的HTML
    parsed_url = urlparse(base_url)
    filename = os.path.basename(remove_trailing_slash(parsed_url.path))
    if not filename:
        filename = 'index.html'
    output_path = os.path.join(output_dir, filename)
    os.makedirs(output_dir, exist_ok=True)
    if output_dir not in downloaded_files:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(str(soup))
            downloaded_files[output_dir] = True
        print("当前页面写入成功")
    else:
        print("当前页面已存在无需写入")
    depth -= 1


# 使用示例
url_a = 'https://www.runoob.com/cprogramming/c-tutorial.html'  # 替换为你要爬取的网页URL
output_dir_a = 'F:\\source'  # 替换为你要保存本地文件的目录
set_depth = 3  # 建议深度3，就是网站跳转的次数最多为3
# 另外除了一开始就爬主站（就是没用path）的主页面是不会爬取主页面的，因为主页面相关链接太多，浪费资源
if not os.path.exists(output_dir_a):
    os.makedirs(output_dir_a)
download_and_replace_recursion(url_a, output_dir_a, url_a)
