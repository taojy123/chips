#!/bin/python

import os
import sys
import datetime
import paramiko
import pymysql
import hashlib
from celery import Celery


SECRET_FIELDS = ['cert_no', 'id_card']


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
        cmd = 'python /home/taojiayuan/workspace/clam/clam.py --encrypt --in %s --key=/root/jiebei.txt' % checkpoint_filename
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

            fpath = os.path.join(today_dir, fname)

            # hard code for 贷前数据
            if fname.endswith('.a'):
                pre_flag = True
                if fname.startswith('check_accounting'):
                    tname = 'jb_join_key'
                elif fname.startswith('check_arg_status_change'):
                    tname = 'jb_verify_first'
                elif fname.startswith('check_daily_balance'):
                    tname = 'jb_verify_final'
                else:
                    assert False, ('贷前数据 未找到对应表', fname)
            else:
                pre_flag = False
                if fname.startswith('check_'):
                    continue
                if '.' in fname:
                    continue
                if '_' not in fname:
                    continue
                tname = fname[:-9]

            print(fname, tname)

            sql = "select count(*) from import_history where fname='%s';" % fname
            print(sql)
            cursor.execute(sql)
            r = cursor.fetchone()
            count = r[0]
            if count > 0:
                print('exists!')
                continue

            try:
                lines = open(fpath).readlines()
            except Exception as e:
                print(fpath, 'try encoding by gbk')
                lines = open(fpath, encoding='gbk').readlines()
            
            # hard code for jb_join_key
            if tname == 'jb_join_key':
                lines = ['id_card,apply_no'] + lines

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

                first_line = lines[0]

                # hard code for 贷前数据
                if tname == 'jb_verify_first':
                    first_line = 'id,create_date,create_user,update_date,update_user,version,bank_code,inst_code,id_card,risk_score,risk_warn,risk_level,fico_score,first_reason,first_credit_limit,first_credit_rate,first_result,rule_random,credit_random,refuse_code,refuse_reason,rs_result,zm_authflag,zm_has_jbadmit,zm_score,zm_curr_address,zm_is_matched,zm_auth_flag,home_code,birthday,gender'
                elif tname == 'jb_verify_final':
                    first_line = 'id,create_date,create_user,update_date,update_user,version,bank_code,inst_code,apply_no,credit_limit,credit_rate,jb_credit_limit,jb_credit_rate,result_'

                fields = first_line.strip().split(',')
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

                    # hard code for 贷前数据
                    if pre_flag:
                        values = line.strip('"').split('","')

                    # hard code for jb_join_key
                    if tname == 'jb_join_key':
                        values = line.split('\t')
                        if len(values) != 2:
                            continue

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


