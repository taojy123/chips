from celery.schedules import crontab

broker_url = 'redis://127.0.0.1:6379/2'
result_backend = 'redis://127.0.0.1:6379/3'

timezone = 'Asia/Shanghai'

result_expires = 3600 * 24 * 7

imports = [
	'jiebei_task',
]


beat_schedule = {
	'fetch': {
		'task': 'jiebei_task.fetch',
		'args': (),
		# 'schedule': crontab(minute='*/2'),
		'schedule': crontab(minute=1, hour='*/6'),
	}
}


