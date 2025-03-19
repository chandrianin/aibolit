import datetime
import zoneinfo

import pytz
from tzlocal import get_localzone
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from aibolit import settings
from app.models import Schedule


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
        user_id = post.get("id")

        # Заполнены ли поля
        if medicament == "" or post.get("interval") == "" or user_id == "":
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
        if len(user_id) != 16 or not user_id.isdigit():
            errorText += "Номер полиса состоит из 16 цифр. "

        if len(errorText) > 0:
            return render(request, post, context={"error": errorText})

        now = datetime.datetime.now(tz=zoneinfo.ZoneInfo(key=settings.TIME_ZONE))
        currentTime = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=now.hour, minute=now.minute)
        while not int(currentTime.minute) in [0, 15, 30, 45]:
            currentTime += datetime.timedelta(minutes=1)
        newSchedule = Schedule.objects.create(animalId=user_id,
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
    elif (len(request.GET) == 2 and not request.POST
          and not request.GET.get("user_id") is None
          and not request.GET.get("schedule_id")):
        get = request.GET
        animalId = get.get("user_id")
        user_id = get.get("schedule_id")

        if animalId == "" or user_id == "":
            return HttpResponse("Не все поля заполнены", status=400)
        try:
            dbSchedule = Schedule.objects.get(animalId=animalId, id=user_id)
        except Schedule.DoesNotExist:
            return HttpResponse("Расписание не найдено", status=404)

        now = datetime.datetime.now(tz=zoneinfo.ZoneInfo(key=settings.TIME_ZONE))
        # Время начало текущего дня
        dayStart = datetime.datetime(now.year, now.month, now.day, 8, tzinfo=zoneinfo.ZoneInfo(key=settings.TIME_ZONE))
        # Время завершения текущего дня
        dayEnd = datetime.datetime(now.year, now.month, now.day, 22, tzinfo=zoneinfo.ZoneInfo(key=settings.TIME_ZONE))

        # Последнее отправленное юзеру уведомление
        lastSentNotification = dbSchedule.lastSentNotification.astimezone(pytz.timezone("UTC"))
        # Время, после которого расписание перестает действовать
        lastPlannedNotification = dayEnd if dbSchedule.lastPlannedNotificationLimit is None \
            else dbSchedule.lastPlannedNotificationLimit.astimezone(pytz.timezone("UTC"))
        # Время (в часах) между приёмами лекарства
        interval = dbSchedule.receptionInterval

        notifications = [dbSchedule.medicamentName]

        while lastSentNotification <= dayEnd and lastSentNotification <= lastPlannedNotification:
            # Если дата уведомления находится раньше, чем начало текущего дня
            # и следующее уведомление должно произойти в течение того же дня
            if ((lastSentNotification + datetime.timedelta(
                    hours=interval)).hour <= 22 and
                    lastSentNotification + datetime.timedelta(hours=interval) < dayStart):
                lastSentNotification += datetime.timedelta(hours=interval)

            # Если дата уведомления находится раньше, чем начало текущего дня
            # и следующее уведомление должно произойти на следующий день
            elif (lastSentNotification + datetime.timedelta(
                    hours=interval)).hour > 22 and lastSentNotification + datetime.timedelta(hours=interval) < dayStart:
                temp = (lastSentNotification + datetime.timedelta(days=1))
                lastSentNotification = (datetime.datetime(temp.year, temp.month, temp.day, hour=8)
                                        + (datetime.datetime(lastSentNotification.year,
                                                             lastSentNotification.month,
                                                             lastSentNotification.day,
                                                             hour=22)
                                           - lastSentNotification))

            # Если уведомление должно прийти в текущий день
            elif lastSentNotification > dayStart:
                notifications.append(lastSentNotification.astimezone(get_localzone()))
                lastSentNotification += datetime.timedelta(hours=interval)

            else:
                return HttpResponse("Произошла ошибка")
        return HttpResponse("<br>".join(map(str, notifications)))
    else:
        return HttpResponse('Некорректные данные', status=400)


# Возвращает список идентификаторов существующих
# расписаний для указанного пользователя
def schedules(request):
    if not request.POST and not request.GET.get("user_id") is None:
        user_id = request.GET.get("user_id")
        if len(user_id) != 16 or not user_id.isdigit:
            return HttpResponse("ID введен некорректно")
        temp = Schedule.objects.filter(animalId=user_id)
        if not temp:
            return HttpResponse(f"Расписаний для id:{user_id} не найдено", status=404)
        return HttpResponse("<br>".join([str(i.id) for i in temp]))

    return HttpResponse("Not Good", status=400)
