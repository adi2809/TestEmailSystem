"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const BACKEND_URL = "http://127.0.0.1:8000";

type EmailStatus = "auto" | "review";

type Email = {
  id: number;
  student_name?: string | null;
  subject: string;
  body: string;
  confidence: number; // 0–1
  status: EmailStatus;
  suggested_reply: string;
  received_at: string;
};

type ConfidenceBucket = {
  range: string;
  count: number;
  percentage: number;
};

type ReviewBucket = {
  name: string;
  value: number;
  color: string;
};

export default function AnalyticsTab() {
  const [emails, setEmails] = useState<Email[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // --- Fetch all emails from backend ---
  useEffect(() => {
    async function fetchEmails() {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`${BACKEND_URL}/emails`);
        if (!res.ok) {
          throw new Error("Failed to fetch emails");
        }
        const data: Email[] = await res.json();
        setEmails(data);
      } catch (err) {
        console.error(err);
        setError("Could not load analytics data");
      } finally {
        setLoading(false);
      }
    }

    fetchEmails();
  }, []);

  const total = emails.length;

  // --- Confidence distribution buckets (REAL, from DB) ---
  const bucketDefs = [
    { label: "0–60%", min: 0.0, max: 0.6 },
    { label: "60–80%", min: 0.6, max: 0.8 },
    { label: "80–95%", min: 0.8, max: 0.95 },
    { label: "95–100%", min: 0.95, max: 1.01 },
  ];

  const bucketCounts = new Array(bucketDefs.length).fill(0);
  for (const e of emails) {
    const c = e.confidence ?? 0;
    let idx = 0;
    if (c < 0.6) idx = 0;
    else if (c < 0.8) idx = 1;
    else if (c < 0.95) idx = 2;
    else idx = 3;
    bucketCounts[idx] += 1;
  }

  const confidenceDistribution: ConfidenceBucket[] = bucketDefs.map((b, i) => {
    const count = bucketCounts[i];
    const percentage = total > 0 ? Math.round((count / total) * 100) : 0;
    return {
      range: b.label,
      count,
      percentage,
    };
  });

  // --- Review breakdown (REAL: review emails by confidence bucket) ---
  const reviewEmails = emails.filter((e) => e.status === "review");
  const reviewTotal = reviewEmails.length;

  const reviewLow = reviewEmails.filter((e) => e.confidence < 0.6).length;
  const reviewMedium = reviewEmails.filter(
    (e) => e.confidence >= 0.6 && e.confidence < 0.8,
  ).length;
  const reviewHigh = reviewEmails.filter(
    (e) => e.confidence >= 0.8,
  ).length;

  const reviewReasons: ReviewBucket[] = [
    {
      name: "Low confidence (<60%)",
      value: reviewLow,
      color: "#ef4444",
    },
    {
      name: "Medium confidence (60–80%)",
      value: reviewMedium,
      color: "#f59e0b",
    },
    {
      name: "High confidence (≥80%)",
      value: reviewHigh,
      color: "#3b82f6",
    },
  ];

  // --- Key insight numbers (REAL) ---
  const lowConfAll = emails.filter((e) => e.confidence < 0.8).length;
  const lowConfPercent = total > 0 ? Math.round((lowConfAll / total) * 100) : 0;

  const pendingCount = reviewTotal;
  const pendingPercent = total > 0 ? Math.round((pendingCount / total) * 100) : 0;

  if (loading && !emails.length && !error) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-foreground">Analytics</h2>
        <p className="text-muted-foreground mt-1">Loading analytics…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-foreground">Analytics</h2>
        <p className="text-red-600 mt-1">{error}</p>
      </div>
    );
  }

  if (!total) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-foreground">Analytics</h2>
        <p className="text-muted-foreground mt-1">
          No emails yet — analytics will appear once emails start flowing into the system.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-foreground">Analytics</h2>
        <p className="text-muted-foreground mt-1">
          Email processing insights and trends (based on real data)
        </p>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Confidence Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Confidence Distribution</CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              How many emails fall into each confidence bracket
            </p>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={confidenceDistribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="range" stroke="#6b7280" />
                <YAxis stroke="#6b7280" />
                <Tooltip
                  contentStyle={{ backgroundColor: "#f3f4f6", border: "1px solid #d1d5db" }}
                  formatter={(value, name) =>
                    name === "count" ? [`${value} emails`, "Count"] : [value, name]
                  }
                />
                <Bar dataKey="count" fill="#3b82f6" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-6 grid grid-cols-2 gap-4">
              {confidenceDistribution.map((item) => (
                <div key={item.range} className="text-sm">
                  <p className="text-muted-foreground">{item.range}</p>
                  <p className="font-semibold text-foreground">
                    {item.count} ({item.percentage}%)
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Review Confidence Breakdown (not fake reasons anymore) */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Review Confidence Breakdown</CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              How confidence scores are distributed among emails that still need manual review
            </p>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={reviewReasons}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value }) =>
                    reviewTotal > 0 ? `${name}: ${value}` : "No review emails"
                  }
                  outerRadius={100}
                  dataKey="value"
                >
                  {reviewReasons.map((entry) => (
                    <Cell key={`cell-${entry.name}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) =>
                    `${value as number} review email${(value as number) === 1 ? "" : "s"}`
                  }
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="mt-6 space-y-2">
              {reviewReasons.map((item) => (
                <div key={item.name} className="flex items-center gap-2">
                  <div
                    className="h-3 w-3 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-sm text-foreground">{item.name}</span>
                  <span className="ml-auto text-sm font-semibold text-muted-foreground">
                    {item.value}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Insights */}
      <Card className="bg-blue-50 border-blue-200">
        <CardHeader>
          <CardTitle className="text-lg text-blue-900">Key Insights</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-4">
            <div className="text-3xl font-bold text-blue-600">
              {lowConfPercent}%
            </div>
            <p className="text-sm text-blue-800">
              of all emails have confidence below 80%. You may want to adjust thresholds
              or expand the knowledge base for these queries.
            </p>
          </div>
          <div className="flex gap-4">
            <div className="text-3xl font-bold text-blue-600">
              {pendingPercent}%
            </div>
            <p className="text-sm text-blue-800">
              of emails are currently pending manual review ({pendingCount} out of {total}).
              As you approve more replies, this percentage will decrease.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}