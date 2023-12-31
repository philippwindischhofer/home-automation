import datetime

def get_current_time():
    return datetime.datetime.now()

def get_timestamp(timeval):
    return timeval.strftime("%d/%m/%y %H:%M:%S")

def measure_time_ms(start, end):
    return (end - start) / datetime.timedelta(milliseconds = 1)
    
def get_current_timestamp():
    return get_timestamp(get_current_time())
