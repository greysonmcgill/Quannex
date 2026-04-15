"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  TrendingUp,
  Settings2,
  Shield,
  Activity,
  Bell,
  HelpCircle,
  FolderUp,
  Users,
} from "lucide-react";

const navigation = [
  { name: "Overview", href: "/", icon: LayoutDashboard },
  { name: "Accounts", href: "/accounts", icon: Users },
  { name: "Upload", href: "/upload", icon: FolderUp },
  { name: "Operations", href: "/operations", icon: Settings2 },
  { name: "Compliance", href: "/compliance", icon: Shield },
  { name: "Executive", href: "/executive", icon: TrendingUp },
];

const secondaryNav = [
  { name: "System Health", href: "/health", icon: Activity },
  { name: "Alerts", href: "/alerts", icon: Bell },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 bg-card border-r">
      <div className="flex h-full flex-col">
        {/* Logo */}
        <div className="flex h-16 items-center gap-2 px-6 border-b">
          <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
            <span className="text-primary-foreground font-bold text-lg">Q</span>
          </div>
          <div>
            <h1 className="font-bold text-lg">Quannex</h1>
            <p className="text-xs text-muted-foreground">Collections OS</p>
          </div>
        </div>

        {/* Main Navigation */}
        <nav className="flex-1 space-y-1 px-3 py-4">
          <p className="px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Dashboards
          </p>
          {navigation.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                <item.icon className="h-5 w-5" />
                {item.name}
              </Link>
            );
          })}

          <div className="pt-4">
            <p className="px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              Monitoring
            </p>
            {secondaryNav.map((item) => {
              const isActive = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  <item.icon className="h-5 w-5" />
                  {item.name}
                </Link>
              );
            })}
          </div>
        </nav>

        {/* Footer */}
        <div className="border-t p-4">
          <div className="flex items-center gap-3 px-3 py-2 text-sm text-muted-foreground">
            <HelpCircle className="h-5 w-5" />
            <span>Documentation</span>
          </div>
          <div className="px-3 mt-2">
            <p className="text-xs text-muted-foreground">
              Quannex Recovery v0.1.0
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}
