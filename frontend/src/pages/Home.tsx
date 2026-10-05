const concepts = [
  {
    title: "Обратный подбор",
    text: "Работодатель находит подтверждённую категорию и сам направляет приглашение с уровнем зарплаты — без вала откликов.",
  },
  {
    title: "Категория = специализация × грейд",
    text: "Категория определяется обязательным путём при регистрации: опрос → выбор грейда → тест. Не по самоописанию в резюме.",
  },
  {
    title: "Гибридное тестирование",
    text: "Параметрическая генерация заданий + калибровка сложности + адаптивная выдача + контроль показов заданий.",
  },
  {
    title: "Объяснимость выдачи",
    text: "Каждый кандидат в подборке получает обоснование: результат теста, достижения, свежесть профиля, соответствие потребности.",
  },
  {
    title: "Контакты по согласию",
    text: "Работодатель не видит контакты кандидата до принятия приглашения или самостоятельного отклика.",
  },
  {
    title: "Работа без истории ФСП",
    text: "Отсутствие подтверждённых достижений обрабатывается явно: блок помечается «нет данных», ничего не додумывается.",
  },
];

export function HomePage() {
  return (
    <div>
      <p className="mb-3 inline-block rounded-full border border-slate-700 px-3 py-1 text-xs uppercase tracking-widest text-cyan-300">
        Хакатон · MVP
      </p>
      <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
        Платформа обратного подбора ИТ-специалистов
      </h1>
      <p className="mt-3 max-w-3xl text-slate-400">
        Соискатели распределяются по категориям на основе объективно подтверждаемого профиля.
        Работодатель находит нужную категорию и сам выходит на конкретного человека с предложением
        и уровнем заработной платы.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {concepts.map((item) => (
          <section key={item.title} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <h2 className="text-sm font-semibold text-sky-300">{item.title}</h2>
            <p className="mt-2 text-sm text-slate-400">{item.text}</p>
          </section>
        ))}
      </div>

      <div className="mt-8 rounded-xl border border-dashed border-slate-700 bg-slate-900/40 p-4 text-sm text-slate-400">
        <strong className="text-slate-200">Статус: Этап 0 — каркас.</strong> Поднят backend (FastAPI,
        health-пробы, OpenAPI), frontend (SPA), слой хранения и mock-провайдеры. Сквозные сценарии
        кабинетов реализуются на следующих этапах.
      </div>
    </div>
  );
}
