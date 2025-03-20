import datetime
import zoneinfo

from tzlocal import get_localzone
from aibolit.settings import TIME_ZONE, DAY_START_HOUR, DAY_END_HOUR


# Заполняет массив из приемов таблеток в период времени между start и end.
# Возвращает дату и время последнего уведомления перед текущим временем, если таковое нашлось. Иначе - None
def pills_in_range(start, end, last_sent_notification, last_planned_notification, interval, notifications):
    new_last_notification = None
    now = datetime.datetime.now(tz=zoneinfo.ZoneInfo(key=TIME_ZONE))
    now_day_start = datetime.datetime(now.year,
                                      now.month,
                                      now.day,
                                      hour=DAY_START_HOUR,
                                      tzinfo=zoneinfo.ZoneInfo(key=TIME_ZONE))
    while last_sent_notification <= end and last_sent_notification <= last_planned_notification:
        # Ищем новую опорную точку для будущего подсчёта времени уведомлений
        if last_sent_notification > now_day_start and new_last_notification is None:
            new_last_notification = last_sent_notification

        current_day_start = datetime.datetime(last_sent_notification.year,
                                              last_sent_notification.month,
                                              last_sent_notification.day,
                                              hour=DAY_START_HOUR,
                                              tzinfo=zoneinfo.ZoneInfo(key=TIME_ZONE))
        current_day_end = datetime.datetime(last_sent_notification.year,
                                            last_sent_notification.month,
                                            last_sent_notification.day,
                                            hour=DAY_END_HOUR,
                                            tzinfo=zoneinfo.ZoneInfo(key=TIME_ZONE))
        next_day_start = current_day_start + datetime.timedelta(days=1)
        next_notification = last_sent_notification + datetime.timedelta(hours=interval)

        # Если дата и время уведомления находятся раньше, чем начало искомого интервала
        # и следующее уведомление должно произойти в течение того же дня
        if last_sent_notification < start and next_notification <= current_day_end:
            last_sent_notification += datetime.timedelta(hours=interval)

        # Если дата и время уведомления находятся раньше, чем начало искомого интервала
        # и следующее уведомление должно произойти этой ночью
        elif last_sent_notification < start and current_day_end < next_notification < next_day_start:
            last_sent_notification = next_day_start

        # Если дата и время уведомления находятся раньше, чем начало искомого интервала
        # и следующее уведомление должно произойти на следующий день
        elif last_sent_notification < start and next_notification >= next_day_start:
            last_sent_notification = next_notification

        # Если уведомление должно произойти в текущем интервале
        elif last_sent_notification >= start and current_day_start <= last_sent_notification <= current_day_end:
            notifications.append(last_sent_notification.astimezone(get_localzone()).strftime("%Y-%m-%d %H:%M"))
            last_sent_notification += datetime.timedelta(hours=interval)
    return new_last_notification
