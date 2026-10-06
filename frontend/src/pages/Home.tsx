import { Link } from "react-router-dom";

import { AIPanel } from "../components/ai";
import { Button, Card, SectionNote } from "../components/ui";

/**
 * Посадочная страница.
 *
 * Читается за минуту и отвечает на три вопроса: что это, как устроен путь сторон,
 * что можно проверить прямо сейчас. Демо-доступы вынесены явно — судья должен
 * попасть в кабинеты без переписки с командой.
 */

/** Путь каждой стороны: обязательные шаги, а не самоописание. */
const ROUTES: { role: string; accent: string; steps: string[]; result: string }[] = [
  {
    role: "Соискатель",
    accent: "text-emerald-300",
    steps: ["Короткий опрос", "Выбор грейда", "Адаптивный тест", "Подтверждённая категория"],
    result:
      "Категория — специализация × грейд — выводится из результата теста, а не из текста резюме. Она же открывает подбор без вала откликов.",
  },
  {
    role: "Работодатель",
    accent: "text-sky-300",
    steps: ["Потребность", "Подборка с обоснованием", "Приглашение с зарплатой", "Контакты по согласию"],
    result:
      "Работодатель видит готовые категории, получает объяснимую подборку и выходит на человека сам. Контакты раскрываются только после согласия.",
  },
];

const PRINCIPLES = [
  {
    title: "Обратный подбор",
    text: "Работодатель находит подтверждённую категорию и сам направляет приглашение с уровнем зарплаты — без вала откликов.",
  },
  {
    title: "Объяснимость выдачи",
    text: "У каждого кандидата в подборке видна причина: результат теста, достижения ФСП, свежесть профиля, соответствие потребности — с вкладом каждого критерия.",
  },
  {
    title: "Контакты по согласию",
    text: "Контакты недоступны до принятия приглашения или самостоятельного отклика. Это правило платформы, а не настройка отображения.",
  },
  {
    title: "Работа без истории ФСП",
    text: "Отсутствие подтверждённых достижений обрабатывается явно: критерий помечается «нет данных» с вкладом 0 и позицию не понижает.",
  },
  {
    title: "Гибридное тестирование",
    text: "Параметрическая генерация заданий, калибровка сложности, адаптивная выдача и контроль показов — против заучивания и утечек.",
  },
  {
    title: "Данные не покидают контур",
    text: "ИИ-слой работает на локальной модели: персональные данные не уходят во внешние сервисы, а при недоступности модели платформа честно переходит на демо-данные.",
  },
];

/** Что реально можно проверить в кабинетах — по ролям. */
const WORKS: { role: string; items: string[] }[] = [
  {
    role: "Соискатель",
    items: [
      "обязательный путь «опрос → грейд → адаптивный тест → категория», продолжение незавершённого теста с того же задания",
      "профиль и ФСП: форма, PDF-резюме с автораспознаванием, генерация PDF, переключатель приватности",
      "приглашения с решением, отклики на вакансии, короткие задания",
      "дашборд: заполненность профиля, категория, θ, приглашения по статусам — у каждой цифры пояснение по клику",
    ],
  },
  {
    role: "Работодатель",
    items: [
      "потребность → подборка с объяснением каждого кандидата, включая отказ от приглашённых ранее",
      "поиск по банку по категории, приглашение с зарплатой и отзыв приглашения",
      "вакансии с откликами и решениями, короткие задания с проверкой решений",
      "дашборд: запросы, приглашения по статусам, доля ответов «ответили N из M»",
    ],
  },
  {
    role: "Администратор",
    items: [
      "воронка пути кандидата и ликвидность рынка: доля потребностей, дошедших до приглашения, время до первого ответа",
      "баланс по категориям «специализация × грейд» с объяснением состояний и активность компаний",
      "схема взаимодействия сторон: связи компаний и соискателей, окрашенные по статусу",
      "ИИ-сводка и рекомендации: модель объясняет уже посчитанные метрики",
    ],
  },
];

const DEMO = [
  { role: "Соискатель", email: "anna.kovaleva@demo.ru" },
  { role: "Работодатель", email: "hr@fintech-demo.ru" },
  { role: "Администратор", email: "admin@demo.ru" },
];

export function HomePage() {
  return (
    <div className="space-y-6">
      <section>
        <p className="inline-block rounded-full border border-slate-700 px-3 py-1 text-xs tracking-widest text-cyan-300 uppercase">
          Хакатон · MVP
        </p>
        <h1 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
          Платформа обратного подбора ИТ-специалистов
        </h1>
        <p className="mt-3 max-w-3xl text-slate-400">
          Соискатели распределяются по категориям на основе объективно подтверждаемого профиля, а
          работодатель находит нужную категорию и сам выходит на конкретного человека с
          предложением и уровнем заработной платы.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Link to="/login">
            <Button>Войти в кабинет</Button>
          </Link>
          <Link to="/health">
            <Button variant="ghost">Состояние стенда</Button>
          </Link>
          <span className="text-xs text-slate-500">
            демо-стенд: три роли, данные сброшены к чистому состоянию
          </span>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-sky-300">Путь каждой стороны</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {ROUTES.map((route) => (
            <Card key={route.role}>
              <h3 className={`text-sm font-semibold ${route.accent}`}>{route.role}</h3>
              <ol className="mt-3 space-y-2">
                {route.steps.map((step, index) => (
                  <li key={step} className="flex items-center gap-2 text-sm text-slate-200">
                    <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-700 text-[11px] text-slate-400">
                      {index + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
              <p className="mt-3 text-xs leading-relaxed text-slate-400">{route.result}</p>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-sky-300">Что уже работает</h2>
        <div className="grid gap-3 md:grid-cols-3">
          {WORKS.map((block) => (
            <Card key={block.role}>
              <h3 className="text-sm font-semibold text-slate-200">{block.role}</h3>
              <ul className="mt-2 space-y-1.5 text-xs leading-relaxed text-slate-400">
                {block.items.map((item) => (
                  <li key={item}>· {item}</li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      </section>

      <AIPanel
        title="ИИ-слой на локальной модели"
        hint="Модель не считает метрики и не подменяет подбор: ранжирование идёт по данным платформы, а модель формулирует вывод словами. Если она недоступна, показываются подготовленные данные с пометкой — сценарий демонстрации не ломается."
      >
        <ul className="space-y-1.5 text-xs leading-relaxed text-slate-300">
          <li>· соискателю — черновик сопроводительного письма и подсказки близких вакансий</li>
          <li>· работодателю — черновик потребности и текста предложения, объяснение кандидата словами</li>
          <li>· администратору — сводка состояния платформы и рекомендации по показателям</li>
          <li>· профиль — разбор текста резюме в поля профиля</li>
        </ul>
      </AIPanel>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-sky-300">Принципы</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {PRINCIPLES.map((item) => (
            <section key={item.title} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <h3 className="text-sm font-semibold text-sky-300">{item.title}</h3>
              <p className="mt-2 text-xs leading-relaxed text-slate-400">{item.text}</p>
            </section>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-sky-300">Как проверить за пару минут</h2>
        <SectionNote>
          Демо-пароль у всех трёх ролей один: <code className="text-sky-300">demo12345</code>. Стенд
          содержит 8 соискателей с пройденным тестом, 2 компании с потребностями, 3 опубликованные
          вакансии с откликами и приглашения во всех статусах — этого достаточно, чтобы увидеть
          воронку, ликвидность, схему взаимодействия и решение по отклику без ручной подготовки данных.
          В шапке кабинета видно, какая модель активна, а у каждой цифры есть знак «?» с пояснением.
        </SectionNote>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {DEMO.map((account) => (
            <Card key={account.email}>
              <p className="text-xs text-slate-400">{account.role}</p>
              <p className="mt-1 font-medium break-all text-slate-200">{account.email}</p>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
