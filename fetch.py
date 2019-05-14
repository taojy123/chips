#!/bin/python

import os
import datetime
import paramiko
import pymysql


client = paramiko.Transport(('10.11.73.11', 22))
client.connect(username='qwuser', password='qwftp')
sftp = paramiko.SFTPClient.from_transport(client)

# sftp.listdir('./kunlunjiebei')
# ['20190505', '20190504', '20190426', '20190510', '20190513', '20190501', '20190512', '20190511', 
# '20190427', '20190425', '20190506', '20190502', '20190503', '20190430', '20190514', '20190429', 
# '20190428', '20190509', '20190507', '20190508']


today = datetime.datetime.now().strftime('%Y%m%d')
print('today is', today)

assert today in sftp.listdir('./kunlunjiebei'), 'data of %s not found!' % today

sftp.get('./kunlunjiebei/%s/%s.tar.Z' % (today, today), '/usr/local/data/checkpoint/jiebei/%s.tar.Z' % today)
print('save to checkpoint success!')

today_dir = '/home/taojiayuan/workspace/%s' % today

if not os.path.exists(today_dir):
    os.makedirs(today_dir)

sftp.get('./kunlunjiebei/%s/%s.tar.Z' % (today, today), '%s/data.tar.Z' % today_dir)


cmd = 'cd %s && tar -Zxvf data.tar.Z && rm -f data.tar.Z' % today_dir
print(cmd)
os.system(cmd)

print('fetch success!')


# for fname in os.listdir(today_dir):

#     yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y%m%d')
#     if yesterday not in fname:
#         continue
#     tname = fname.replace('_' + yesterday, '')

#     fpath = os.path.join(today_dir, fname)
#     tpath = os.path.join('/usr/local/data/data_jiebei', tname)

#     cmd = 'cp %s %s' % (fpath, tpath)
#     print(cmd)
#     # os.system(cmd)

# print('copy to data_jiebei success!')


conn =  pymysql.connect(host="172.23.43.13", port=3307, user="tjy", password='tjy', database='jiebei', charset='utf8')
cursor = conn.cursor()

for fname in os.listdir(today_dir):

    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y%m%d')

    assert yesterday in fname, (yesterday, fname)

    tname = fname.replace('_' + yesterday, '')

    if tname.startswith('check_'):
        continue

    print(tname)
    if tname not in ['loan_daily']:
        print('skip')
        continue

    fpath = os.path.join(today_dir, fname)
    lines = open(fpath).read().strip().splitlines()

    fields = lines[0].split(',')
    fieldstr = ', '.join(fields)

    for line in lines[1:]:

        values = line.split(',')
        valuestr = "', '".join(values)
        valuestr = "'" + valuestr + "'"

        sql = "insert into %s (%s) values (%s);" % (tname, fieldstr, valuestr) 
        print(sql)
        cursor.execute(sql)

cursor.execute('commit;')
cursor.close()
conn.close()

print('upload to mysql success!')


