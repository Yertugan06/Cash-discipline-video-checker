# Анкета на золотых кадрах
Всего проверок: 56, верно: 44 (79%); не найдено кадров: 0

| Поле | Верно | Всего | Точность |
|---|---|---|---|
| key_in_safe_lock | 0 | 2 | 0% |
| desk_cash | 1 | 3 | 33% |
| room_door | 1 | 2 | 50% |
| clients_at_desk | 2 | 4 | 50% |
| laptop_screen | 4 | 7 | 57% |
| cashier_action | 2 | 3 | 67% |
| people_cashier_side | 2 | 3 | 67% |
| cashier_at_desk | 14 | 14 | 100% |
| safe_door | 6 | 6 | 100% |
| desk_bag | 2 | 2 | 100% |
| desk_personal_items | 2 | 2 | 100% |
| desk_food_drink | 2 | 2 | 100% |
| counting_machine_in_use | 1 | 1 | 100% |
| collector_present | 1 | 1 | 100% |
| id_document_visible | 1 | 1 | 100% |
| detector_in_use | 2 | 2 | 100% |
| desk_documents | 1 | 1 | 100% |

## Ошибки
| Видео | t | Поле | Ожидалось | Модель | Комментарий |
|---|---|---|---|---|---|
| X-29 | 12.0 | laptop_screen | lock_screen | unlocked | экран блокировки (норма) |
| X-22 | 17.0 | key_in_safe_lock | yes | not_visible | ключ со связкой в замке (нарушение) |
| X-22 | 17.0 | laptop_screen | lock_screen | off_or_closed |  |
| X-23 | 16.0 | key_in_safe_lock | no | not_visible | ключ забран (норма) |
| X-23 | 16.0 | laptop_screen | lock_screen | unlocked |  |
| X-26 | 11.0 | desk_cash | true | false | пачка на столе (нарушение) |
| X-32 | 10.0 | room_door | open | closed | дверь не закрыта (нарушение) |
| X-33 | 12.0 | people_cashier_side | 2 | 1 | мужчина в белой рубашке за спиной кассира |
| X-18 | 21.0 | clients_at_desk | 2 | 1 | второй человек подаёт карточку |
| X-38 | 33.0 | desk_cash | true | false | пачка прошлого клиента на столе |
| X-44 | 16.0 | cashier_action | counting_by_hand | seated_idle |  |
| X-35 | 30.0 | clients_at_desk | 1 | 0 |  |