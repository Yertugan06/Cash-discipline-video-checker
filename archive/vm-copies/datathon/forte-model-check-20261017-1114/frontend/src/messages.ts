export function warningText(value: string, language: 'ru' | 'en'): string {
  if (language === 'ru') return value;
  const translations: Array<[string, string]> = [
    ['Рабочая и клиентская зоны', 'Cashier/client zones could not be calibrated confidently. Manual zones are needed.'],
    ['Роль кассира', 'The cashier role could not be assigned confidently. Related checks are limited.'],
    ['Есть сессии', 'Some sessions started before a visible entry. Earlier document presentation cannot be assessed.'],
    ['Наличные не распознаны', 'Cash was not detected confidently. Money-flow checks are limited.'],
    ['Не хватает уверенных', 'Reliable hand points were insufficient. Item transfers may have been missed.'],
  ];
  const translated = translations.find(([prefix]) => value.startsWith(prefix));
  if (translated) return translated[1];
  if (value.startsWith('Не локализованы объекты сцены:')) {
    return `Scene objects not located: ${value.split(':').slice(1).join(':').trim()}`;
  }
  const state = /^Состояние (\w+) часто/.exec(value);
  if (state) return `The state of ${state[1]} was often unclear; related checks are limited.`;
  return value;
}
