import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type MonthPoint = { month: string; revenue: number };

export function RevenueTrendChart({ data }: { data: MonthPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 12, right: 18, left: 2, bottom: 0 }}>
        <CartesianGrid stroke="#edf0f5" vertical={false} />
        <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: "#8790a1", fontSize: 11 }} dy={9} />
        <YAxis hide domain={["dataMin - 30000", "dataMax + 30000"]} />
        <Tooltip formatter={(value) => formatCurrency(Number(value))} contentStyle={{ border: "1px solid #e9edf3", borderRadius: 10, fontSize: 12 }} />
        <Line type="monotone" dataKey="revenue" stroke="#5369e8" strokeWidth={2.7} dot={{ r: 3.5, fill: "#fff", stroke: "#5369e8", strokeWidth: 2 }} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function MonthlyRevenueChart({ data }: { data: MonthPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 9, left: -13, bottom: 0 }}>
        <CartesianGrid stroke="#edf0f5" vertical={false} />
        <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: "#8790a1", fontSize: 11 }} dy={8} />
        <YAxis axisLine={false} tickLine={false} tick={{ fill: "#8790a1", fontSize: 10 }} tickFormatter={(value) => `$${Math.round(Number(value) / 1000)}k`} />
        <Tooltip formatter={(value) => formatCurrency(Number(value))} contentStyle={{ border: "1px solid #e9edf3", borderRadius: 10, fontSize: 12 }} />
        <Bar dataKey="revenue" radius={[4, 4, 0, 0]}>
          {data.map((row) => <Cell key={row.month} fill={row.month === "Sep" ? "#f2a15f" : "#6374e8"} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function EvaluationTrendChart({ data }: { data: { run: string; answer: number; retrieval: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 12, right: 12, left: -19, bottom: 0 }}>
        <CartesianGrid stroke="#edf0f5" vertical={false} />
        <XAxis dataKey="run" axisLine={false} tickLine={false} tick={{ fill: "#8790a1", fontSize: 11 }} />
        <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: "#8790a1", fontSize: 10 }} tickFormatter={(value) => `${value}%`} />
        <Tooltip formatter={(value) => `${Number(value).toFixed(1)}%`} contentStyle={{ border: "1px solid #e9edf3", borderRadius: 10, fontSize: 12 }} />
        <Line dataKey="answer" name="Answer correctness" stroke="#6374e8" strokeWidth={2.5} dot={{ r: 3 }} />
        <Line dataKey="retrieval" name="Retrieval relevance" stroke="#36a98b" strokeWidth={2.5} dot={{ r: 3 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}
