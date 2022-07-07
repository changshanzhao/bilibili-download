import time
import requests
import json
import os
import re
from lxml import html
import subprocess
import threading

headers = {
    'user-agent': 'Mozilla/5.0',
    'Referer': 'https://www.bilibili.com/'
}


# get视频名字得到搜索到的数据
def get_name():
    name = input('请输入你要爬取的视频：')
    url = f'https://search.bilibili.com/video?keyword={name}'
    str_get_name = requests.get(url).text
    # 获取总页数
    pages_li = html.etree.HTML(str_get_name).xpath('//*[@id="video-list"]/div[2]/div/ul/li')
    page_max = pages_li[len(pages_li) - 2].xpath('button/text()')[0].strip()
    print(f'总共有{page_max}页')
    # 存储翻页了的所有的视频和标题
    all_video_title = []
    num = 1  # 默认第一页
    number = 1  # 每一个视频的序号
    # 最多只能换页面这些次
    while num <= int(page_max):
        url = f'https://search.bilibili.com/video?keyword={name}&page={num}'
        # 请求翻页的页数的url
        get_page = requests.get(url).text
        # xpath获取获取翻页的所有视频url和标题
        href_li = html.etree.HTML(get_page).xpath('/html/body/div[3]/div/div[2]/div/ul/li/a/@href')
        title_li = html.etree.HTML(get_page).xpath('/html/body/div[3]/div/div[2]/div/ul/li/a/@title')
        href_li01 = ['https:' + i for i in href_li]
        # 将获取的数据整合为dict格式
        dict_video = dict(zip(title_li, href_li01))
        for i in dict_video:
            # 将每一个视频信息存储到all_video_title中
            all_video_title.append([i, dict_video[i]])
            print(f'序号:{number}', i, dict_video[i])
            number += 1
        # 换页操作
        while True:
            num01 = input('是否换页？')
            if num01 == 'yes' or num01 == 'YES':
                num += 1  # 页数换取
                break
            elif num01 == 'no' or num01 == 'NO':
                return [all_video_title, number - 1]
            else:
                print('请输入正确的 yes 或 no，请重新输入')
                continue


# 获取爬取序号范围内的视频,data[0]是获取的页数的所有视频 data[1]通过换页得到的最大序号
def get_num_scope(data):
    while True:
        try:
            start = int(input('输入开始要爬取的序号：'))
            end = int(input('输入结束要爬取的序号：'))
            if 0 < start <= end <= int(data[1]):
                return data[0][start - 1:end]
            else:
                print('输入的序号逻辑出现问题！')
        except ValueError:
            print('程序出错')


# 该函数连接了单视频-多视频的批量爬取(通过提前将数据准备好在一次性全部执行) -- 后期可修改为多线程爬取
# get选择好了的视频(这里还需要设置一个同步爬取，这样就不需要等待当前爬取的视频结束后在操作了)
def access_choose(data):
    list01 = []  # 存储的是所有单视频的数据 [url, 视频标题]
    list02 = []  # 存储的是所有多视频的数据 [url, 视频标题] 处理得到list03
    list03 = []  # 存储的是所有多视频的数据 [url, 视频标题,开始爬取集数, 结束爬取集数]
    for i in data:  # i[0]标题 i[1]url
        # 单集视频
        if not html.etree.HTML(requests.get(i[1]).text).xpath(
                '/html/body/div[2]/div[4]/div[2]/div[4]/div[1]/div[1]/h3'):
            # 将视频标题和url作为参数传入
            list01.append([i[1], i[0]])
        # 多集视频
        else:
            # 将视频标题和url作为参数传入
            list02.append([i[1], i[0]])
    # 先把多集数的视频，把他爬取视频范围一次性搞出来
    for i in list02:  # i[0]url  i[1]视频名字
        # 每一个视频的总集数
        set_len = len(html.etree.HTML(requests.get(i[0]).text).xpath('//*[@id="multi_page"]/div[2]/ul/li'))
        print(f'{i[1]}的总集数有：', set_len)
        # 每一个视频的爬取集数范围
        while True:
            try:
                start = int(input(f'对于{i[1]}输入开始爬取的集数：'))
                end = int(input(f'对于{i[1]}输入结束爬取的集数：'))
                if 0 < start <= end <= set_len:
                    # 将视频url,视频标题,开始爬取集数,结束爬取集数存入list03
                    list03.append([i[0], i[1], start, end])
                    break
                else:
                    print('集数输入逻辑出错，请重新输入！')
            except ValueError:
                print('程序出错！')
    print('单视频有：', list01)
    print('多视频有：', list03)
    # 如果其中获得的单视频不为空，那么就遍历调用单视频爬取函数
    # 存储所有外部视频线程对象(还不包括集数线程对象)
    thread01 = []
    if list01:
        for i in list01:
            thread01.append(threading.Thread(target=more_video, args=(i[0], i[1])))
            # more_video(i[0], i[1])  # 调用了这个函数的线程
    # 如果其中获得的多视频不为空，那么就遍历调用多视频爬取函数
    if list03:
        for i in list03:
            thread01.append(threading.Thread(target=double_video, args=(i[0], i[1], i[2], i[3])))
    for i in thread01:
        i.start()  # 开启线程
    for i in thread01:
        i.join()  # 关闭线程


# 单视频爬取,然后调用保存mp3和mp4的函数(这里参数使用了可变参数,因为多集还需要传入集数的标题,单集的只需要视频标题就行了)
def more_video(url, *title):
    re_video_str = re.findall('<script>window.__playinfo__=(.*?)</script>', requests.get(url).text)[0]
    jsonVideo = json.loads(re_video_str)  # 转换为json格式的数据
    # 单视频的音频url不变的
    audio_url = jsonVideo['data']['dash']['audio'][0]['baseUrl']
    # 视频清晰度和对应的id
    clarity, id01 = jsonVideo['data']['accept_description'], jsonVideo['data']['accept_quality']
    # 将id个视频清晰度作为字典对象,方便等会的提示
    dict_clarity_id = dict(zip(id01, clarity))
    print('该视频清晰度有：', dict_clarity_id)
    # 得到所有的视频数据列表
    all_video_data = jsonVideo['data']['dash']['video']
    # 设置一个存放最大id值变量
    max_id = 0
    # 直接获取视频的最高清晰度id(b站规律,第一个id就是能爬取到的最大值)
    for i in all_video_data:
        max_id = i['id']
        break
    print(f'视频默认获取的最高视频清晰度：', dict_clarity_id[max_id])
    # 遍历单视频的json格式数据，将max_clarity清晰度的视频提取出来
    for i2 in all_video_data:
        if max_id == i2['id']:
            # 调用保存本地的函数(参数: 音频url,视频url,标题(集数或视频))
            save_mp3_mp4(audio_url, i2['baseUrl'], title)
            break


# 多视频爬取,得到后就将每一集的url再次调用单视频爬取
def double_video(url, title, kaishi, jieshu):
    # 这里获取每一集视频的名字
    get_set_str = requests.get(url).text
    # 通过筛选得到每一集的集标题数据
    json_re = json.loads(re.findall(r'<script>window.__INITIAL_STATE__=(.*?);\(function\(\)', get_set_str)[0])
    # 得到真正的所有集标题列表数据(下边在传输标签的时候就可以通过索引来获取)
    ji_list_title = [i.get('part') for i in json_re['videoData']['pages']]
    thread02 = []  # 存储集数线程对象
    for i in range(kaishi, jieshu + 1):
        # 遍历得到获取的集数的url
        url = url.split('?')[0] + f'?p={i}'
        thread02.append(threading.Thread(target=more_video, args=(url, title, ji_list_title[i - 1])))
    for i in thread02:
        i.start()  # 开启线程
    for i in thread02:
        i.join()  # 关闭线程


# 存储音频、视频(的title参数在单集和多集中是不一样的)
def save_mp3_mp4(mp3_url, mp4_url, title):
    # 设置条件，来处理传入的参数(如果标题长度为2，则是有集数对应的视频，否则是单个视频)
    if len(title) == 2:
        # 调用重命名格式函数--得到的视频标题和集数标题
        title01 = named(title[0])
        set_title = named(title[1])
        path_create = fr'D:/爬取的数据/bilibili/分集/{title01}/'
        path_generate = fr'D:/爬取的数据/bilibili/分集/{title01}/{set_title}'
        if not os.path.exists(f'{path_create}'):
            os.makedirs(fr'{path_create}')
        with open(fr'{path_generate}.mp3', 'wb') as f1:
            f1.write(requests.get(mp3_url, headers=headers).content)
            time.sleep(3)
            print(f'{title01}的{set_title} ---  音频爬取成功！')
        f1.close()
        with open(fr'{path_generate}.mp4', 'wb') as f2:
            f2.write(requests.get(mp4_url, headers=headers).content)
            time.sleep(3)
            print(f'{title01}的{set_title} ---  视频爬取成功！')
        f2.close()
        # 将创建好的路径作为参数传入
        merge(path_generate)
    else:
        # 调用重命名格式函数--得到的视频标题，这是单视频存储
        title = named(str(title[0]))
        path_create = fr'D:/爬取的数据/bilibili/单集/{title}/'
        path_generate = fr'D:/爬取的数据/bilibili/单集/{title}/{title}'
        if not os.path.exists(fr'{path_create}'):
            os.makedirs(fr'{path_create}')
        with open(fr'{path_generate}.mp3', 'ab') as f1:
            time.sleep(3)
            f1.write(requests.get(mp3_url, headers=headers).content)
            print(f'{title} --音频爬取成功！')
        f1.close()
        with open(fr'{path_generate}.mp4', 'ab') as f2:
            time.sleep(3)
            f2.write(requests.get(mp4_url, headers=headers).content)
            print(f'{title} -- 视频爬取成功！')
        f2.close()
        # 调用合并文件函数(将路径传入)
        merge(path_generate)


# 设置命名格式正则的sub方法作用: 特殊字符转换为_
def named(title):
    return re.sub(r'[?\\/:!<>|"\s]', '_', title)


# 合并视频(传入的参数是视频路径,不过这个前缀不包括.mp3这些结尾)
def merge(path_generate):
    mp3_address = fr'{path_generate}.mp3'
    mp4_address = fr'{path_generate}.mp4'
    merge_address = fr'{path_generate}--合并.mp4'
    com = f'ffmpeg -i {mp3_address} -i {mp4_address} -c:v copy -c:a aac -strict experimental {merge_address}'
    subprocess.Popen(com, shell=True)
    print(f'{merge_address}合并成功！')


def main():
    # get要搜搜的名字，最终返回搜索的页数的所有数据
    page_data = get_name()
    # 批量爬取，得到搜索范围的数据
    start_end = get_num_scope(page_data)
    # 现在开始正式访问自己选择了的视频
    access_choose(start_end)


if __name__ == '__main__':
    main()