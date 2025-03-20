import datetime
import zoneinfo

import pytz
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from aibolit import settings
from app.models import Schedule
from app.pillsTime import pills_in_range


def schedule(request):
    # В ответ роут должен возвращать идентификатор (id) созданного расписания из базы данных
    if (not request.GET
            and len(request.POST) == 5
            and not request.POST.get("medicament") is None
            and not request.POST.get("id") is None
            and not request.POST.get("interval") is None
            and not request.POST.get("duration") is None):

        errorText = ""

        post = request.POST
        medicament = post.get("medicament")
        schedule_id = post.get("id")

        # Заполнены ли поля
        if medicament == "" or post.get("interval") == "" or schedule_id == "":
            return render(request, 'post.html', context={"error": "Заполнены не все поля"}, status=400)

        # Интервал - число?
        if not post.get("interval").isdigit():
            return render(request, 'post.html', context={"error": "Интервал приема введен некорректно"}, status=400)
        interval = int(post.get("interval"))

        # Продолжительность приёма введена?
        if post.get("duration") == "":
            duration = 0
        elif not post.get("duration").isdigit():
            return render(request, 'post.html', context={"error": "Продолжительность приема введена некорректно"},
                          status=400)
        else:
            duration = int(post.get("duration"))

        # Корректно ли название медикамента
        if len(medicament) > 30:
            errorText += "Название лекарства должно быть короче 30 символов. "

        # Входит ли интервал в необходимые границы
        if interval > 24 or interval < 1:
            errorText += "Интервал приема лекарства должен быть от 1 до 24-х часов. "

        # Продолжительность записана корректно?
        if duration <= 0 and post.get("duration") != "":
            errorText += "Продолжительность приёма должна быть не может быть неположительной. "

        # Проверка записи номера полиса (id)
        if len(schedule_id) != 16 or not schedule_id.isdigit():
            errorText += "Номер полиса состоит из 16 цифр. "

        if len(errorText) > 0:
            return render(request, post, context={"error": errorText})

        now = datetime.datetime.now(tz=zoneinfo.ZoneInfo(key=settings.TIME_ZONE))
        current_day_start = datetime.datetime(now.year,
                                              now.month,
                                              now.day,
                                              hour=settings.DAY_START_HOUR,
                                              tzinfo=zoneinfo.ZoneInfo(key=settings.TIME_ZONE))
        current_day_end = datetime.datetime(now.year,
                                            now.month,
                                            now.day,
                                            hour=settings.DAY_END_HOUR,
                                            tzinfo=zoneinfo.ZoneInfo(key=settings.TIME_ZONE))
        next_day_start = current_day_start + datetime.timedelta(days=1)
        currentTime = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=now.hour, minute=now.minute,
                                        tzinfo=zoneinfo.ZoneInfo(key=settings.TIME_ZONE))
        while not int(currentTime.minute) in [0, 15, 30, 45]:
            currentTime += datetime.timedelta(minutes=1)
        if current_day_end < currentTime < next_day_start:
            currentTime = next_day_start
        newSchedule = Schedule.objects.create(animalId=schedule_id,
                                              medicamentName=medicament,
                                              lastSentNotification=currentTime,
                                              lastPlannedNotificationLimit=(currentTime + timezone.timedelta(
                                                  days=duration)) if duration > 0 else None,
                                              receptionInterval=interval
                                              )
        return HttpResponse(newSchedule.id)

    # Отправлен запрос без параметров
    elif not request.GET and not request.POST:
        return render(request, 'post.html')

    # Возвращает данные о выбранном расписании с рассчитанным
    # графиком приёмов на день
    elif (len(request.GET) == 2
          and not request.POST
          and not request.GET.get("user_id") is None
          and not request.GET.get("schedule_id") is None):
        get = request.GET
        animal_id = get.get("user_id")
        schedule_id = get.get("schedule_id")

        if animal_id == "" or schedule_id == "":
            return HttpResponse("Не все поля заполнены", status=400)
        try:
            dbSchedule = Schedule.objects.get(animalId=animal_id, id=schedule_id)
        except Schedule.DoesNotExist:
            return HttpResponse("Расписание не найдено", status=404)

        now = datetime.datetime.now(tz=zoneinfo.ZoneInfo(key=settings.TIME_ZONE))
        # Время начало текущего дня
        dayStart = datetime.datetime(now.year,
                                     now.month,
                                     now.day,
                                     settings.DAY_START_HOUR,
                                     tzinfo=zoneinfo.ZoneInfo(key=settings.TIME_ZONE))
        # Время завершения текущего дня
        dayEnd = datetime.datetime(now.year,
                                   now.month,
                                   now.day,
                                   settings.DAY_END_HOUR,
                                   tzinfo=zoneinfo.ZoneInfo(key=settings.TIME_ZONE))

        # Последнее отправленное юзеру уведомление
        lastSentNotification = dbSchedule.lastSentNotification.astimezone(pytz.timezone("UTC"))

        # Время, после которого расписание перестает действовать
        lastPlannedNotification = dayEnd if dbSchedule.lastPlannedNotificationLimit is None \
            else dbSchedule.lastPlannedNotificationLimit.astimezone(pytz.timezone("UTC"))

        # Время (в часах) между приёмами лекарства
        interval = dbSchedule.receptionInterval

        notifications = [dbSchedule.medicamentName]
        new_notification = pills_in_range(dayStart, dayEnd, lastSentNotification, lastPlannedNotification, interval,
                                          notifications)

        if new_notification is not None and new_notification != lastSentNotification:
            dbSchedule.lastSentNotification = new_notification
            dbSchedule.save(update_fields=["lastSentNotification"])

        return HttpResponse("<br>".join(map(str, notifications)))
    else:
        return HttpResponse('Некорректные данные', status=400)


# Возвращает список идентификаторов существующих
# расписаний для указанного пользователя
def schedules(request):
    if len(request.GET) == 1 and not request.POST and not request.GET.get("user_id") is None:
        user_id = request.GET.get("user_id")
        if len(user_id) != 16 or not user_id.isdigit:
            return HttpResponse("ID введен некорректно")
        schedulesSet = Schedule.objects.filter(animalId=user_id)
        if not schedulesSet:
            return HttpResponse(f"Расписаний для id:{user_id} не найдено", status=404)
        return HttpResponse("<br>".join([str(i.id) for i in schedulesSet]))

    return HttpResponse('Некорректные данные', status=400)


# Возвращает данные о таблетках, которые необходимо принять
# в ближайший период (settings.PILLS_NEAREST_TIME).
def next_takings(request):
    if len(request.GET) == 1 and not request.POST and not request.GET.get("user_id") is None:
        user_id = request.GET.get("user_id")
        if len(user_id) != 16 or not user_id.isdigit:
            return HttpResponse("ID введен некорректно")

        pillsStart = datetime.datetime.now(tz=zoneinfo.ZoneInfo(key=settings.TIME_ZONE))
        while not int(pillsStart.minute) in [0, 15, 30, 45]:
            pillsStart += datetime.timedelta(minutes=1)
        pillsEnd = pillsStart + datetime.timedelta(hours=settings.PILLS_NEAREST_TIME)

        schedulesSet = Schedule.objects.filter(animalId=user_id)
        nearestPills = {}
        for scheduleElem in schedulesSet:
            # Последнее отправленное юзеру уведомление
            lastSentNotification = scheduleElem.lastSentNotification.astimezone(pytz.timezone("UTC"))

            # Время, после которого расписание перестает действовать
            lastPlannedNotification = pillsStart if scheduleElem.lastPlannedNotificationLimit is None \
                else scheduleElem.lastPlannedNotificationLimit.astimezone(pytz.timezone("UTC"))

            # Время (в часах) между приёмами лекарства
            interval = scheduleElem.receptionInterval

            notifications = []
            new_notification = pills_in_range(pillsStart, pillsEnd, lastSentNotification, lastPlannedNotification,
                                              interval, notifications)
            if new_notification is not None and new_notification != lastSentNotification:
                scheduleElem.lastSentNotification = new_notification
                scheduleElem.save(update_fields=["lastSentNotification"])
            nearestPills[scheduleElem.medicamentName] = notifications

        result = ""
        for item in nearestPills.items():
            if item[1]:
                result += f"{item[0]}: {item[1][0]}<br>"
        return HttpResponse(result)
    return HttpResponse("Некорректные данные", status=400)
