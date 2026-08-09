async function loadStats() {
    try {
        const res = await fetch('/admin/api/stats');
        const data = await res.json();

        document.getElementById('total-orders').innerText = data.total_orders;
        document.getElementById('total-revenue').innerHTML = '&#8377;' + data.total_revenue.toLocaleString('en-IN');
        document.getElementById('total-products').innerText = data.total_products;

        const list = document.getElementById('recent-orders-list');
        list.innerHTML = data.recent_orders.length ? data.recent_orders.map(order => `
            <tr class="hover:bg-teal-50/10 transition-colors group">
                <td class="px-10 py-6 font-mono text-xs font-bold text-gray-400 group-hover:text-teal-600 transition-colors">#${order._id.slice(-6).toUpperCase()}</td>
                <td class="px-10 py-6 italic">
                    <span class="font-extrabold text-[#0f172a] text-sm not-italic">${order.user_name || order.user_email || 'Guest'}</span>
                </td>
                <td class="px-10 py-6">
                    <span class="px-4 py-1.5 bg-gray-100 text-gray-600 text-[9px] font-black rounded-full uppercase tracking-widest border border-gray-200">
                        ${order.status || 'Placed'}
                    </span>
                </td>
                <td class="px-10 py-6 text-right font-black text-[#0f172a] text-sm">&#8377;${order.total || order.total_amount || 0}</td>
            </tr>
        `).join('') : `<tr><td colspan="4" class="px-10 py-12 text-center text-xs font-bold text-gray-300 uppercase tracking-widest">No Recent Activity Recorded</td></tr>`;

    } catch (e) {
        console.error('Stats Sync Error', e);
    }
}

document.addEventListener('DOMContentLoaded', loadStats);
