# -*- coding: utf-8 -*-
import requests
import pandas
import generate_excel
from encodings import utf_8
from bs4 import BeautifulSoup
import xlwt

# 读取网页内容
proxy = {'http': '58.253.157.212:9999'}
headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20100101 Firefox/84.0',
           'cookie': '_uab_collina=160930737494772653755355; JSESSIONID=BFB1E1E649EE8A1CE031075EE0E0BB26; tk=wbQdW_QCHvg9iJysVm5qJ4a-J9AE_v3OdD27fYMK3JYbcD1D0; BIGipServerotn=1324352010.50210.0000; RAIL_EXPIRATION=1609605604064; RAIL_DEVICEID=hOoGafzb48YAh0w6ZvTc9stjFvetESd-gvem4cn88w__9Lpw4u8-MZPvOKg3YCUin4339HIqXJhiu-qW2iNdbqBuJGLqa7DoefbA0MUBqEKqc6eU_c52-xRrxgvbEOeEXQo9XH7uZ698LVGGxEg2kCvF-B1Xbt3o; BIGipServerpool_passport=132383242.50215.0000; route=6f50b51faa11b987e576cdb301e545c4; uKey=2ee6d5fdb429cf3d5ec50ee48d35510a7fc46b9b36cd9879f5d1794ac5ee9df0; current_captcha_type=Z; _jc_save_fromStation=%u5317%u4EAC%2CBJP; _jc_save_toStation=%u5357%u660C%2CNCG; _jc_save_fromDate=2020-12-30; _jc_save_toDate=2020-12-30; _jc_save_wfdc_flag=dc'
           }
# time.sleep(1)→urllib3
url = 'https://kyfw.12306.cn/otn/leftTicket/queryT?leftTicketDTO.train_date=2021-01-05&leftTicketDTO.from_station=LZJ&leftTicketDTO.to_station=JNK&purpose_codes=ADULT'
response = requests.get(url, headers=headers, proxies=proxy)
result = response.json()
# print('抽取之前的所有内容：', result, '\n')
result = result['data']['result']
# print('抽取之后的内容：', result, '\n')


m = 1
# a = 0
# b = 0
sum = pandas.DataFrame()

# 解析结果并存入dict
for i in result:
	# print(i)
	list = i.split('|')
	# print('第', m, '条结果：', list)
	m += 1

	dict = {
		'状态': list[1],
		'车次': list[3],
		'目的地': list[5],
		'出发地': list[6],
		'出发时间': list[8],
		'到达时间': list[9],
		'历时': list[10],
		'软卧一等卧': list[23],
		'硬座二等座': list[26],
		'硬座': list[28],
		'无座': list[29],
	}
	print(dict)
	try:
		# df = pandas.DataFrame.from_dict(dict, orient='index')
		sum = sum.append(dict, ignore_index=True)
		# a += 1
		# b += 2
		# print(dict.values())
		# for value in dict.values():
		#     dict.values().extend(dict.values())


	except Exception as e:
		print(str(e))

# 保存进Excel，用的是DataFrame
file_path = pandas.ExcelWriter('.//dict.xls')
cols = ['状态', '车次', '出发时间', '到达时间', '出发地', '目的地', '历时', '软卧一等卧', '硬座二等座', '硬座', '无座']
sum.to_excel(file_path, "sheet1", startrow=0, startcol=0, encoding='utf-8', columns=cols)
# sum = sum.iloc[:, cols]
file_path.save()

# for key in dict.keys():
#     list.append(key)
#     l = list


# for d in dict:
#     if d == '':
#         d == '--'
#     else:
#         d = d


# generate_excel(dict)


# for a in list:
#     print('编号：', n, '内容：', a)
#     n += 1
# n = 0

# cuo print(type(dict['状态']))


'''
d = {
    '无座': list[29],
    '硬座': list[28],
    '硬座二等座': list[26],
    '软卧一等卧': list[23],
    '历时': list[10],
    '到达时间': list[9],
    '出发时间': list[8],
    '出发地': list[6],
    '目的地': list[5],
    '车次': list[3]
}
print(d)
'''

'''
m = pd.DataFrame(d)
pd.head()
pd.describe_option()
pd.read_excel('dict.xls')
'''

'''
匹配的规律是：dict={'无座':list[29],
'硬座':list[28],
'硬卧二等座':list[26],
'软卧一等卧':list[23],
'历时':list[10],
'到达时间':list[9],
'出发时间':list[8],
'出发地':list[6],
'目的地':list[5-7],
'车次':list[3]}
'''

'''
connect with db(mongodb)
client=pymongo.MongoClient('localhost ',27017) 连接数据库文件 端口号27017
test = client['test'] 创建数据库文件test
tickets = test['tickets'] 创建表tickets
save(parse(request(year,month)))
time.sleep(1) 休眠时间间隔
'''

# 写入Excel文件
def generate_excel(dict,savepath):
	try:
		'''
		m = pd.DataFrame(dict, index=[0])
		print(m.head())
		print(m.describe())
		pd.read_excel('dict.xls')
		'''
		# 创建工作表
		excel = xlwt.Workbook(encoding="utf-8", style_compression=0)
		sheet = excel.add_sheet("今日爬取到的车票情况", cell_overwrite_ok=True)
		col = ['状态', '车次', '出发时间', '到达时间', '出发地', '目的地', '历时', '软卧一等卧', '硬座二等座', '硬座', '无座']
		# 制定写入规则
		for i in range(0, 10):
			sheet.write(0, i, col[i])
			break
		for i in range(0, 100):
			dic = dict[i]
			for j in range(0,10):
				sheet.write(i+1, j,dic[j])
		excel.save(savepath)
	except Exception as e:
		print('异常', str(e))

if __name__ == '__main__':
	generate_excel()



	'''
	sheet.write(0, 0, "状态")
	sheet.write(0, 1, "车次")
	sheet.write(0, 2, "目的地")
	sheet.write(0, 3, "出发地")
	sheet.write(0, 4, "出发时间")
	sheet.write(0, 5, "到达时间")
	sheet.write(0, 6, "历时")
	sheet.write(0, 7, "软卧一等卧")
	sheet.write(0, 8, "硬座二等座")
	sheet.write(0, 9, "硬座")
	sheet.write(0, 10, "无座")
	row = 1
	col = 0
	
	
	for i in (dict):
		sheet.write(row, col, str(dict['状态']))
		sheet.write(row, col + 1, str(dict['车次']))
		sheet.write(row, col + 2, str(dict['目的地']))
		sheet.write(row, col + 3, str(dict['出发地']))
		sheet.write(row, col + 4, str(dict['出发时间']))
		sheet.write(row, col + 5, str(dict['到达时间']))
		sheet.write(row, col + 6, str(dict['历时']))
		sheet.write(row, col + 7, str(dict['软卧一等卧']))
		sheet.write(row, col + 8, str(dict['硬座二等座']))
		sheet.write(row, col + 9, str(dict['硬座']))
		sheet.write(row, col + 10, str(dict['无座']))
		excel.save('dic.xls')
		row += 1
		excel.close()
	'''

