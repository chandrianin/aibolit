import datetime

import pytz
from django.http import HttpResponse
from django.shortcuts import render
from django.templatetags.tz import utc
from django.utils import timezone

from aibolit import settings
from app.models import Schedule


def schedule(request):
    if len(request.GET) == 0 and len(request.POST) > 0:
        errorText = ""
        post = request.POST
        medicament = post.get("medicament")
        Id = post.get("id")

        if medicament is None or medicament == "" or post.get("interval") is None or post.get(
                "interval") == "" or Id is None or Id == "":
            return render(request, post, context={"error": "Заполнены не все поля"}, status=400)

        if not post.get("interval").isdigit():
            return render(request, post, context={"error": "Интервал приема введен некорректно"})
        interval = int(post.get("interval"))

        if post.get("duration") == "" or post.get("duration") is None:
            duration = 0
        elif not post.get("duration").isdigit():
            return render(request, post, context={"error": "Продолжительность приема введена некорректно"})
        else:
            duration = int(post.get("duration"))

        if len(medicament) > 30:
            errorText += "Название лекарства должно быть короче 30 символов. "

        if interval > 24 or interval < 1:
            errorText += "Интервал приема лекарства должен быть от 1 до 24-х часов. "

        if duration == 0 and post.get("duration") != "" and not post.get("duration") is None:
            errorText += "Продолжительность приёма должна быть или больше 1. "

        if len(Id) != 16 or not Id.isdigit():
            errorText += "Номер полиса состоит из 16 цифр. "

        if len(errorText) > 0:
            return render(request, post, context={"error": errorText})

        now = datetime.datetime.now(tz=pytz.timezone(settings.TIME_ZONE))
        currentTime = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=now.hour, minute=now.minute)
        while not int(currentTime.minute) in [0, 15, 30, 45]:
            currentTime += datetime.timedelta(minutes=1)
        newSchedule = Schedule.objects.create(animalId=Id,
                                              medicamentName=medicament,
                                              lastSentNotification=currentTime,
                                              lastPlannedNotificationLimit=(currentTime + timezone.timedelta(
                                                  days=duration)) if duration > 0 else None,
                                              receptionInterval=interval
                                              )
        # В ответ роут должен возвращать идентификатор (id) созданного
        # расписания из базы данных
        return HttpResponse(newSchedule.id)

    elif len(request.GET) == 0 and len(request.POST) == 0:
        return render(request, 'post.html')
    elif len(request.GET) == 2 and len(request.POST) == 0:
        # Какие-то действия с БД.
        get = request.GET
        animalId = get.get("user_id")
        Id = get.get("schedule_id")

        if animalId is None or animalId == "" or Id is None or Id == "":
            return HttpResponse("Не все поля заполнены", status=400)
        try:
            dbSchedule = Schedule.objects.get(animalId=animalId, id=Id)
        except Schedule.DoesNotExist:
            return HttpResponse("Расписание не найдено", status=404)

        lastNotification = dbSchedule.lastSentNotification
        interval = dbSchedule.receptionInterval
        now = datetime.datetime.now(tz=pytz.timezone(settings.TIME_ZONE))
        dayStart = datetime.datetime(now.year, now.month, now.day, 8, tzinfo=pytz.timezone(settings.TIME_ZONE))
        dayEnd = datetime.datetime(now.year, now.month, now.day, 22, tzinfo=pytz.timezone(settings.TIME_ZONE))
        notifications = []
        # TODO добавить lastPlanned
        while lastNotification < dayEnd:
            if (lastNotification + datetime.timedelta(
                    hours=interval)).hour <= 22 and lastNotification + datetime.timedelta(hours=interval) < dayStart:
                lastNotification += datetime.timedelta(hours=interval)
            elif (lastNotification + datetime.timedelta(
                    hours=interval)).hour > 22 and lastNotification + datetime.timedelta(hours=interval) < dayStart:
                temp = (lastNotification + datetime.timedelta(days=1))
                lastNotification = datetime.datetime(temp.year, temp.month, temp.day, hour=8) + (
                        datetime.datetime(lastNotification.year, lastNotification.month, lastNotification.day,
                                          hour=22) - lastNotification)
            elif lastNotification > dayStart:
                notifications.append(lastNotification)
                lastNotification += datetime.timedelta(hours=interval)

        # Возвращает данные о выбранном расписании с рассчитанным
        # графиком приёмов на день
        return HttpResponse("<br>".join(map(str, notifications)))
    else:
        return HttpResponse('Некорректные данные')
