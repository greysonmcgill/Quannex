"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { DashboardData, SystemHealth, Alert } from "@/lib/api";

interface WebSocketMessage {
  type: "initial" | "update" | "metric_update" | "pong";
  data?: Partial<DashboardData> | { health: SystemHealth; alerts: Alert[] };
  metric?: string;
  value?: number;
  timestamp?: string;
}

interface UseWebSocketOptions {
  url?: string;
  onMessage?: (message: WebSocketMessage) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  lastMessage: WebSocketMessage | null;
  sendMessage: (message: object) => void;
  reconnect: () => void;
}

export function useWebSocket({
  url = `ws://${typeof window !== "undefined" ? window.location.host : "localhost:8000"}/api/v1/dashboard/ws`,
  onMessage,
  reconnectInterval = 5000,
  maxReconnectAttempts = 5,
}: UseWebSocketOptions = {}): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (typeof window === "undefined") return;

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;

        // Start ping interval
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
          }
        }, 25000);
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);
          onMessage?.(message);
        } catch (error) {
          console.error("Failed to parse WebSocket message:", error);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;

        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Attempt reconnection
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current += 1;
            connect();
          }, reconnectInterval);
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
      };

      wsRef.current = ws;
    } catch (error) {
      console.error("Failed to create WebSocket:", error);
    }
  }, [url, onMessage, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const reconnect = useCallback(() => {
    disconnect();
    reconnectAttemptsRef.current = 0;
    connect();
  }, [connect, disconnect]);

  const sendMessage = useCallback((message: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    sendMessage,
    reconnect,
  };
}

// Hook for dashboard-specific real-time updates
export function useDashboardUpdates(
  onUpdate?: (data: Partial<DashboardData>) => void
) {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);

  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      if (message.type === "initial" || message.type === "update") {
        const data = message.data as { health?: SystemHealth; alerts?: Alert[] };
        if (data?.health) setHealth(data.health);
        if (data?.alerts) setAlerts(data.alerts);
        onUpdate?.(message.data as Partial<DashboardData>);
      }
    },
    [onUpdate]
  );

  const { isConnected, reconnect } = useWebSocket({
    onMessage: handleMessage,
  });

  return {
    isConnected,
    health,
    alerts,
    reconnect,
  };
}
