# Анкета состояний (features) v1

На каждый кадр VLM заполняет JSON по схеме [`schema/questionnaire_v1.json`](schema/questionnaire_v1.json):
- значения берутся только из перечислений, `true/false` или чисел;
- сервер принуждает модель к этой схеме (structured output);
- промпт с определениями полей лежит в [`prompts/questionnaire.txt`](prompts/questionnaire.txt).

Связь с нормами: поле → событие/состояние в таймлайне → правило в [`scripts/timeline_rules.py`](scripts/timeline_rules.py) → ID нормы из [`codex/codex_verified.json`](codex/codex_verified.json).

| Поле | Значения | Что значит | Где используется (правило → норма) | Проверяется золотом |
|---|---|---|---|---|
| `cashier_at_desk` | bool | кассир на рабочем месте у стола (сидит или стоит) | уход с места → `leave_*` (231 п. 20 ч. 2, п. 22, п. 80; 53 п. 71) | X-28, X-29, X-22, X-23, X-20, X-21, X-26, X-27, X-15, X-12, X-11, X-35 |
| `cashier_in_room` | bool | кассир вообще в комнате (например, у сейфа) | момент выхода из комнаты: ключ, ноутбук | косвенно |
| `people_cashier_side` | 0–5 | людей на стороне кассира, включая кассира (клиенты напротив не считаются) | `outsider` (14 п. 16 пп. 1), п. 8) | X-30, X-31, X-33 |
| `clients_at_desk` | 0–5 | людей на клиентской стороне стола | сессии клиента, `two_clients`, `dirty_desk`, `client_left_count`, `no_id` | X-18, X-37, X-34, X-35 |
| `person_at_door` | bool | кто-то входит или выходит прямо сейчас | точный момент прихода нового клиента | — |
| `collector_present` | bool | инкассатор в комнате (зелёная сумка, тёмная куртка) | `collector_quick` (231 п. 24); исключение для `outsider` | X-17 |
| `desk_cash` | bool | купюры или пачки лежат на столе (не в машине) | `leave_cash`, `dirty_desk`, `merge_cash` (231 п. 20 ч. 2) | X-26, X-27, X-38 |
| `desk_bag` | bool | инкассаторская сумка на столе | `leave_cash`, `collector_quick` | X-15, X-17 |
| `desk_documents` | bool | бумаги, папка, планшет на столе | `leave_docs` (231 п. 80, п. 2 пп. 17)) | X-24 |
| `desk_personal_items` | bool | пальто, сумка, рюкзак, кошелёк | `personal_items` (231 п. 12 ч. 1) | X-40, X-43 |
| `desk_food_drink` | bool | еда, стакан, бутылка | `food` (231 п. 12 ч. 2) | X-46, X-43 |
| `phone_in_cashier_hand` | bool | телефон в руке кассира | `phone` (231 п. 12 ч. 2 — связь с камерой) | — (нет в датасете) |
| `id_document_visible` | bool | удостоверение в руке или на столе | `no_id` (231 п. 19 пп. 1), п. 7) | X-2 |
| `counting_machine_in_use` | bool | деньги в счётной машине или её лотке | `client_left_count` (231 п. 20 ч. 1), `bag_to_safe_no_count` | X-34 |
| `detector_in_use` | bool | купюры на детекторе | `no_detector` (эксперимент; 231 п. 19 пп. 2)) | X-45, X-44 |
| `safe_door` | open / closed / not_visible | дверца сейфа | `safe_open` (231 п. 20 ч. 2) | X-20, X-21, X-22, X-23, X-35, X-39 |
| `key_in_safe_lock` | yes / no / not_visible | ключ торчит из замка сейфа | `leave_key` (231 п. 80) | X-22, X-23 |
| `laptop_screen` | unlocked / lock_screen / off_or_closed / not_visible | экран ноутбука | `leave_laptop` (53 п. 71 пп. 9), косвенная) | X-28, X-29, X-22, X-23, X-12, X-11 |
| `room_door` | open / closed / not_visible | стеклянная дверь кабины | `door_open` (14 п. 16 пп. 1), п. 8, косвенная) | X-31, X-32 |
| `cash_in_hands_of` | nobody / cashier / client / collector / several | у кого в руках купюры | `no_id`, `merge_cash` | — |
| `cashier_action` | 16 значений | главное действие кассира | `at_safe` для ключа и сейфа, `counting_*`, `eating_drinking`, `using_phone`, `packing_or_opening_bag` | X-46, X-44, X-1 |
| `other` | строка | необычное, по-русски, одно предложение | `other_to_codex.py`: поиск по кодексу → ID или NONE (новые типы) | — |

## Как расширять под новые типы финала
1. Выберите норму на листе «Новые типы» в `research/Кодекс_норм.xlsx`. Её сигналы уже указаны в колонке «Сигналы для системы».
2. Если сигнала нет в анкете, добавьте поле в схему и в промпт. Версию схемы повышайте: `questionnaire_v2.json`.
3. Добавьте правило в `timeline_rules.py` (`TITLE`, `CODEX`, `VERIFY_Q` и логику в `detect`).
4. Добавьте 2–3 строки в `data/gold_states.csv` и, если есть свой ролик, строку в `data/gt_violations.csv`.
