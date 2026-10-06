import { useCallback, useEffect, useRef, useState } from "react";

import * as apiClient from "./client";
import type { Grade, Specialization } from "./client";
import { errorMessage } from "./client";

/**
 * Справочники платформы, загружаемые один раз на компонент.
 *
 * Раньше состояние и эффект загрузки копировались в каждый раздел, где есть выбор
 * специализации или грейда — шесть копий одного и того же кода. Ошибка загрузки не
 * блокирует раздел: справочник остаётся пустым, а форма работает на встроенном
 * списке грейдов.
 */
function useLoaded<T>(load: () => Promise<T[]>): T[] {
  const [rows, setRows] = useState<T[]>([]);
  useEffect(() => {
    let alive = true;
    load()
      .then((data) => {
        if (alive) setRows(data);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
    // load — стабильная ссылка на функцию клиента, перезагрузка не нужна
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return rows;
}

export function useSpecializations(): Specialization[] {
  return useLoaded(() => apiClient.listSpecializations());
}

export function useGrades(): Grade[] {
  return useLoaded(() => apiClient.listGrades());
}

type Resource<T> = {
  data: T;
  error: string | null;
  reload: () => Promise<void>;
  setData: (value: T) => void;
  setError: (message: string | null) => void;
};

/**
 * Загрузка данных раздела: данные, ошибка и повтор.
 *
 * Каркас «вызвать клиент, положить данные, показать ошибку» был скопирован в каждый
 * раздел кабинетов — девять копий, причём часть разделов показывала ошибку врезкой,
 * часть уведомлением. Каркас стал один; как показать ошибку, по-прежнему решает
 * раздел: для этого есть `onError`.
 *
 * `initial` нужен там, где раздел до загрузки рисует пустой список, а не надпись
 * «Загружаю…» — поведение остаётся прежним.
 */
export function useResource<T>(loader: () => Promise<T>): Resource<T | null>;
export function useResource<T>(
  loader: () => Promise<T>,
  options: { initial: T; onError?: (message: string) => void },
): Resource<T>;
export function useResource<T>(
  loader: () => Promise<T>,
  options?: { initial?: T; onError?: (message: string) => void },
): Resource<T | null> {
  const [data, setData] = useState<T | null>(options?.initial ?? null);
  const [error, setError] = useState<string | null>(null);
  // Загрузчик и обработчик ошибки держим в ссылках: вызывающие передают стрелки,
  // и зависимость от них перезапускала бы загрузку на каждом рендере.
  const loaderRef = useRef(loader);
  const onErrorRef = useRef(options?.onError);
  loaderRef.current = loader;
  onErrorRef.current = options?.onError;

  const reload = useCallback(async () => {
    try {
      setData(await loaderRef.current());
    } catch (err) {
      const message = errorMessage(err);
      setError(message);
      onErrorRef.current?.(message);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, reload, setData, setError };
}
