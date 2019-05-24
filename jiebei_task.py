#!/bin/python

import os
import sys
import datetime
import paramiko
import pymysql
import hashlib
from celery import Celery


SECRET_FIELDS = ['cert_no']


app = Celery('jiebei')
app.config_from_object('celeryconfig')


@app.task
def fetch(is_all=False):

    client = paramiko.Transport(('10.11.73.11', 22))
    client.connect(username='qwuser', password='qwftp')
    sftp = paramiko.SFTPClient.from_transport(client)

    conn =  pymysql.connect(host="172.23.43.13", port=3307, user="tjy", password='tjy', database='jiebei', charset='utf8')
    cursor = conn.cursor()

    total_counter = 0

    if is_all:
        days = sftp.listdir('./kunlunjiebei')
        days = sorted(days)
        # ['20190505', '20190506', '20190510', ...]
    else:
        today = datetime.datetime.now().strftime('%Y%m%d')
        days = [today]

    for today in days:

        print('today is', today)
        if today not in sftp.listdir('./kunlunjiebei'):
            result = 'data of %s not found!' % today
            return result

        checkpoint_filename = '/usr/local/data/checkpoint/jiebei/%s.tar.Z' % today
        sftp.get('./kunlunjiebei/%s/%s.tar.Z' % (today, today), checkpoint_filename)
        cmd = 'python /home/taojiayuan/workspace/clam/clam.py --encrypt --in %s --key=/root/abc.txt' % checkpoint_filename
        os.system(cmd)
        os.remove(checkpoint_filename)

        print('save to checkpoint success!')

        today_dir = '/home/taojiayuan/workspace/jiebeitmp/%s' % today

        if not os.path.exists(today_dir):
            os.makedirs(today_dir)

        sftp.get('./kunlunjiebei/%s/%s.tar.Z' % (today, today), '%s/data.tar.Z' % today_dir)


        cmd = 'cd %s && tar -Zxvf data.tar.Z && rm -f data.tar.Z' % today_dir
        print(cmd)
        os.system(cmd)

        print('fetch success!')

        for fname in os.listdir(today_dir):

            if fname.startswith('check_'):
                continue

            if '_' not in fname:
                continue

            if '.' in fname:
                continue

            tname = fname[:-9]
            fpath = os.path.join(today_dir, fname)

            print(fname, tname)

            sql = "select count(*) from import_history where fname='%s';" % fname
            print(sql)
            cursor.execute(sql)
            r = cursor.fetchone()
            count = r[0]
            if count > 0:
                print('exists!')
                continue

            lines = open(fpath).readlines()
            counter = 0

            if tname == 'accounting':
                fields = []
                values = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    field, value = line.split(',')
                    fields.append(field)
                    values.append(value)

                fieldstr = ', '.join(fields)
                valuestr = "', '".join(values)
                valuestr = "'" + valuestr + "'"

                sql = "insert into %s (%s) values (%s);" % (tname, fieldstr, valuestr) 
                print(sql)
                cursor.execute(sql)
                counter += 1

            else:

                fields = lines[0].strip().split(',')
                fieldstr = ', '.join(fields)

                secret_indexs = []
                for secret_field in SECRET_FIELDS:
                    if secret_field in fields:
                        index = fields.index(secret_field)
                        secret_indexs.append(index)

                for line in lines[1:]:

                    line = line.strip()
                    if not line:
                        continue

                    values = line.split(',')

                    for secret_index in secret_indexs:
                        value = values[secret_index]
                        secret_value = hashlib.md5(value.encode()).hexdigest()
                        values[secret_index] = secret_value

                    valuestr = "', '".join(values)
                    valuestr = "'" + valuestr + "'"

                    sql = "insert into %s (%s) values (%s);" % (tname, fieldstr, valuestr) 
                    print(sql)
                    cursor.execute(sql)
                    counter += 1

            sql = "insert into import_history (fname, count) values ('%s', %d);" % (fname, counter) 
            print(sql)
            cursor.execute(sql)
            cursor.execute('commit;')
            total_counter += counter

        print('upload to mysql success!')

        for fname in os.listdir(today_dir):
            fpath = os.path.join(today_dir, fname)
            os.remove(fpath)
        print('remove temp files finish!')

    sftp.close()
    client.close()
    cursor.close()
    conn.close()

    if total_counter:
        result = 'import %d records successful!' % total_counter
    else:
        result = 'No records need to be imported'

    print(result)
    return result


if __name__ == '__main__':

    print('======= manually start up ==========')

    if len(sys.argv) > 1 and sys.argv[1] == 'all':
        fetch(is_all=True)
    else:
        fetch()

# celery multi start w1 -A jiebei_task -B --concurrency=1
# flower -A jiebei_task --address=0.0.0.0
# nohup flower -A jiebei_task --address=0.0.0.0 > /dev/null 2>&1 &


