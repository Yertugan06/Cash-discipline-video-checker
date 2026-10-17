# Анкета на золотых кадрах
Всего проверок: 56, верно: 51 (91%); не найдено кадров: 0

| Поле | Верно | Всего | Точность |
|---|---|---|---|
| key_in_safe_lock | 1 | 2 | 50% |
| room_door | 1 | 2 | 50% |
| cashier_action | 2 | 3 | 67% |
| clients_at_desk | 3 | 4 | 75% |
| laptop_screen | 6 | 7 | 86% |
| cashier_at_desk | 14 | 14 | 100% |
| safe_door | 6 | 6 | 100% |
| desk_cash | 3 | 3 | 100% |
| desk_bag | 2 | 2 | 100% |
| desk_personal_items | 2 | 2 | 100% |
| desk_food_drink | 2 | 2 | 100% |
| people_cashier_side | 3 | 3 | 100% |
| counting_machine_in_use | 1 | 1 | 100% |
| collector_present | 1 | 1 | 100% |
| id_document_visible | 1 | 1 | 100% |
| detector_in_use | 2 | 2 | 100% |
| desk_documents | 1 | 1 | 100% |

## Ошибки
| Видео | t | Поле | Ожидалось | Модель | Комментарий |
|---|---|---|---|---|---|
| X-22 | 17.0 | key_in_safe_lock | yes | no | ключ со связкой в замке (нарушение) |
| X-22 | 17.0 | laptop_screen | lock_screen | off_or_closed |  |
| X-46 | 14.0 | cashier_action | eating_drinking | counting_by_hand |  |
| X-32 | 10.0 | room_door | open | closed | дверь не закрыта (нарушение) |
| X-18 | 21.0 | clients_at_desk | 2 | 1 | второй человек подаёт карточку |