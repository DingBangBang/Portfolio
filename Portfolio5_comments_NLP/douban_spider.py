import urllib
from bs4 import BeautifulSoup
import re
import xlwt

def main():
	baseurl = "https://movie.douban.com/top250?start="
	# 爬取数据
	datalist = GetData(baseurl)
	# 存储数据
	savepath = './/豆瓣电影Top250.xls'
	SaveData(datalist, savepath)


# 影片详情链接/图片/片名/评分/评价人数的规则
findlink = re.compile(r'<a href="(.*?)">')  # 创建正则表达式对象，表示规则
findimgsrc = re.compile(r'<img.*src="(.*?)"', re.S)  # 让换行符也包含在链接中
findtitle = re.compile(r'<span class="title">(.*)</span>')
# findrating = re.compile()
# findjudge = re.compile()


def GetData(baseurl):
	datalist = []

	# 获取指定网页的内容
	try:
		def AskUrl(url):
			proxy = urllib.request.ProxyHandler({'http': '58.253.157.212:9999'})
			opener = urllib.request.build_opener(proxy)  # urllib模块如果使用IP代理就需要写的一句build_opener
			urllib.request.install_opener(opener)
			head = {'User-Agent': 'Mozilla / 5.0(WindowsNT10.0;Win64;x64;rv: 84.0) Gecko / 20100101Firefox / 84.0'}
			request = urllib.request.Request(url, headers=head)  # 发送请求
			response = urllib.request.urlopen(request)  # 收集响应
			html = response.read()  # .deconde(utf_8)  # 读取并格式化html内容
			# print(html)
			return html
	except urllib.error.URLerror as e:
		if hasattr(e, 'code'):
			print(e.code)
		elif hasattr(e, 'reason'):
			print(e.reason)
		else:
			print('unknown exception')

	# 循环爬取所有内容并保存为列表
	for i in range(0, 10):
		url = baseurl + str(i * 25)
		html = AskUrl(url)
	# datalist.append(html)
	# print(datalist)

		# 逐一解析数据
		soup = BeautifulSoup(html, 'html.parser')
		for item in soup.find_all('div', class_='item'):  # 查找符合要求的字符串，（没有循环的话）形成列表
			# print(item) # 测试查看电影item的全部信息
			data = []  # 用于保存一部电影相关的指定信息
			item = str(item)  # 一定要把item中的所有信息转换为str类型，re才可以对其进行操作

			link = re.findall(findlink, item)[0]
			# print(link)
			data.append(link)
			imgsrc = re.findall(findimgsrc, item)[0]
			data.append(imgsrc)
			title = re.findall(findtitle, item)[0]
			data.append(title)

			datalist.append(data)
	# print(datalist)
	return datalist


def SaveData(datalist, savepath):
	print('saving...')
	excel = xlwt.Workbook(encoding='utf-8')
	sheet = excel.add_sheet('豆瓣电影Top250')
	col = ('详情页链接', '图片链接', '电影名称')
	for i in range(0, 3):
		sheet.write(0, i, col[i])
		break
	for i in range(0, 250):
		print('正在打印第%d条' % (i+1))
		data = datalist[i]
		for j in range(0, 3):
			sheet.write(i + 1, j, data[j])
	excel.save(savepath)


if __name__ == '__main__':
	main()
	print('豆瓣Top250网页爬取完毕')
