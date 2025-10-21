import { useEffect, useRef, useState } from "react";
import axios from "axios";

const API_BASE = `http://${window.location.hostname}:8000`;
const WS_BASE  = `ws://${window.location.hostname}:8000`;

export default function App() {
  const [otype, setOtype] = useState("limit");
  const [bbo, setBbo] = useState({ best_bid: null, best_offer: null });
  const [depth, setDepth] = useState({ bids: [], asks: [] });
  const [trades, setTrades] = useState([]);

  const [mdUp, setMdUp] = useState(false);
  const [trUp, setTrUp] = useState(false);

  useEffect(() => {
    const md = new WebSocket(`${WS_BASE}/ws/marketdata/`);
    md.onopen = () => { setMdUp(true); console.log("MarketData WS: open"); };
    md.onclose = () => { setMdUp(false); console.warn("MarketData WS: closed"); };
    md.onerror = (e) => console.error("MarketData WS error", e);
    md.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "bbo") setBbo({ best_bid: msg.best_bid, best_offer: msg.best_offer });
      if (msg.type === "l2")  setDepth({ bids: msg.bids ?? [], asks: msg.asks ?? [] });
    };

    const tr = new WebSocket(`${WS_BASE}/ws/trades/`);
    tr.onopen = () => { setTrUp(true); console.log("Trades WS: open"); };
    tr.onclose = () => { setTrUp(false); console.warn("Trades WS: closed"); };
    tr.onerror = (e) => console.error("Trades WS error", e);
    tr.onmessage = (e) => setTrades((t) => [JSON.parse(e.data), ...t].slice(0, 50));

    return () => { md.close(); tr.close(); };
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
      symbol: "BTC-USDT",
      order_type: fd.get("order_type"),
      side: fd.get("side"),
      quantity: fd.get("quantity"),
    };
    const price = fd.get("price");
    if (payload.order_type !== "market" && price) payload.price = price;

    await axios.post(`${API_BASE}/api/orders/`, payload, { headers: { "Content-Type": "application/json" } });
    e.target.reset();
  };

  const seed = async () => {
    await axios.post(`${API_BASE}/api/orders/`, { symbol:"BTC-USDT", order_type:"limit", side:"sell", quantity:"1",   price:"65000" });
    await axios.post(`${API_BASE}/api/orders/`, { symbol:"BTC-USDT", order_type:"limit", side:"sell", quantity:"1.5", price:"65100" });
    await axios.post(`${API_BASE}/api/orders/`, { symbol:"BTC-USDT", order_type:"limit", side:"buy",  quantity:"2",   price:"64900" });
  };

  const Dot = ({up}) => (
    <span style={{
      display: "inline-block", width: 10, height: 10, borderRadius: 999,
      background: up ? "#16a34a" : "#ef4444", marginLeft: 6
    }} />
  );

  return (
    <div style={{ fontFamily: "Inter, system-ui, sans-serif", padding: 16, display: "grid", gap: 16 }}>
      <h2>Crypto Matching Engine – Demo</h2>

      <div style={{ fontSize: 14 }}>
        MarketData WS <Dot up={mdUp} /> &nbsp;&nbsp; Trades WS <Dot up={trUp} />
      </div>

      <section style={{ display: "flex", gap: 24 }}>
        <div>
          <h3>BBO</h3>
          <div>Best Bid: <b>{bbo.best_bid ?? "-"}</b></div>
          <div>Best Offer: <b>{bbo.best_offer ?? "-"}</b></div>
        </div>

        <div>
          <h3>Top 10 Depth</h3>
          <div style={{ display: "flex", gap: 24 }}>
            <table border="1" cellPadding="4">
              <thead><tr><th colSpan="2">Asks</th></tr><tr><th>Price</th><th>Qty</th></tr></thead>
              <tbody>{(depth.asks || []).map(([p,q]) => <tr key={`a-${p}`}><td>{p}</td><td>{q}</td></tr>)}</tbody>
            </table>
            <table border="1" cellPadding="4">
              <thead><tr><th colSpan="2">Bids</th></tr><tr><th>Price</th><th>Qty</th></tr></thead>
              <tbody>{(depth.bids || []).map(([p,q]) => <tr key={`b-${p}`}><td>{p}</td><td>{q}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      </section>

      <section>
        <h3>Submit Order</h3>
        <form onSubmit={submit} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <select name="order_type" value={otype} onChange={e => setOtype(e.target.value)}>
            <option value="market">Market</option>
            <option value="limit">Limit</option>
            <option value="ioc">IOC</option>
            <option value="fok">FOK</option>
          </select>
          <select name="side" defaultValue="buy">
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
          <input name="quantity" placeholder="Quantity" type="number" step="0.00000001" required />
          <input name="price" placeholder="Price (limit/IOC/FOK)" type="number" step="0.01" disabled={otype === "market"} />
          <button type="submit">Send</button>
        </form>
        <div style={{ marginTop: 8 }}>
          <button onClick={seed}>Seed Book (65000/65100/64900)</button>
        </div>
      </section>

      <section>
        <h3>Recent Trades</h3>
        <table border="1" cellPadding="4">
          <thead><tr><th>Time</th><th>Price</th><th>Qty</th><th>Aggressor</th></tr></thead>
          <tbody>
            {trades.map(t => (
              <tr key={t.trade_id}>
                <td>{t.timestamp}</td><td>{t.price}</td><td>{t.quantity}</td><td>{t.aggressor_side}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
