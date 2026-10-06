import { useEffect, useState } from "react";

import * as apiClient from "./client";
import type { Grade, Specialization } from "./client";

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
