"use client";

import { useCallback, useEffect, useState } from "react";

export interface UseDashboardDataResult<T> {
  data: T;
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;
  refresh: () => void;
}

export function useDashboardData<T>(
  fetcher: () => Promise<T>,
  createEmpty: () => T
): UseDashboardDataResult<T> {
  const [data, setData] = useState<T>(createEmpty);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const result = await fetcher();
      setData(result);
    } catch (err) {
      setData(createEmpty());
      setError(err instanceof Error ? err.message : "Unable to load data");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [fetcher, createEmpty]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const refresh = useCallback(() => {
    setIsRefreshing(true);
    loadData();
  }, [loadData]);

  return { data, isLoading, isRefreshing, error, refresh };
}
