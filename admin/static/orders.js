function formatCurrency(val) {
    try {
        const num = Number(String(val).replace(/[^0-9.-]+/g,"")) || 0;
        return '&#8377;' + num.toLocaleString('en-IN');
    } catch (e) {
        return '&#8377;0';
    }
}

async function loadOrders(force = false) {
    const list = document.getElementById('order-list');
    const badge = document.getElementById('sync-badge');
    if (!list) return;
    
    list.innerHTML = `<tr><td colspan="6" class="text-center py-10"><i class="fas fa-circle-notch fa-spin text-teal-500 text-2xl"></i><p class="text-[10px] font-bold text-gray-400 uppercase mt-4">Syncing</p></td></tr>`;
    
    try {
        const url = '/admin/api/orders?t=' + (force ? Date.now() : new Date().getTime());
        const res = await fetch(url);
        if (!res.ok) throw new Error("Sync Failed");
        
        const orders = await res.json();
        console.log("DIAGNOSTIC: Received from /admin/api/orders ->", orders);

        if (!Array.isArray(orders)) throw new Error("Invalid data format received");

        if (badge) {
            badge.innerText = `Sync: ${orders.length} Records Found`;
            badge.className = `px-2 py-0.5 bg-teal-50 text-teal-600 text-[8px] font-black rounded-full uppercase tracking-tighter transition-all`;
        }

        list.innerHTML = orders.length ? orders.map(o => `
            <tr class="hover:bg-teal-50/10 transition-colors group">
                <td class="px-10 py-6 font-mono text-xs font-bold text-gray-400 group-hover:text-teal-600 transition-colors">#${o._id.slice(-6).toUpperCase()}</td>
                <td class="px-10 py-6">
                    <div class="flex flex-col">
                        <span class="font-extrabold text-[#0f172a] text-sm">${o.user_name || o.user_email || 'Guest'}</span>
                        <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest mt-0.5">${o.created_at || 'N/A'}</span>
                    </div>
                </td>
                <td class="px-10 py-6">
                    <span class="text-xs font-bold text-gray-500 uppercase tracking-wider">${(o.items || []).length} SKU(s)</span>
                </td>
                <td class="px-10 py-6">
                    <div class="relative max-w-[140px]">
                        <select onchange="updateStatus('${o._id}', this.value)" class="w-full pl-4 pr-8 py-2.5 bg-gray-100/30 border border-gray-100 text-[9px] font-black uppercase tracking-widest rounded-full focus:ring-2 focus:ring-teal-500/20 appearance-none cursor-pointer">
                            <option value="Placed" ${o.status === 'Placed' ? 'selected' : ''}>Placed</option>
                            <option value="Processing" ${o.status === 'Processing' ? 'selected' : ''}>Processing</option>
                            <option value="Shipped" ${o.status === 'Shipped' ? 'selected' : ''}>Shipped</option>
                            <option value="Delivered" ${o.status === 'Delivered' ? 'selected' : ''}>Delivered</option>
                            <option value="Cancelled" ${o.status === 'Cancelled' ? 'selected' : ''}>Cancelled</option>
                        </select>
                        <i class="fas fa-chevron-down absolute right-4 top-1/2 -translate-y-1/2 text-[8px] text-gray-400 pointer-events-none"></i>
                    </div>
                </td>
                <td class="px-10 py-6 text-right font-black text-[#0f172a] text-sm">&#8377;${o.total || o.total_amount || 0}</td>
                <td class="px-10 py-6 text-center">
                    <button onclick="viewOrder('${o._id}')" class="w-9 h-9 flex items-center justify-center rounded-full bg-[#0f172a] text-white hover:bg-black transition-all shadow-lg shadow-gray-900/10">
                        <i class="fas fa-search-plus text-xs"></i>
                    </button>
                </td>
            </tr>
        `).join('') : `<tr><td colspan="6" class="px-10 py-12 text-center text-xs font-bold text-gray-300 uppercase tracking-widest">No Fulfillment Records Found</td></tr>`;
    } catch (err) {
        list.innerHTML = `<tr><td colspan="6" class="text-center py-12"><div class="inline-flex flex-col items-center"><i class="fas fa-exclamation-triangle text-amber-500 text-xl mb-4"></i><p class="text-xs font-black text-red-500 uppercase tracking-widest">System Interface Error</p><p class="text-[9px] text-gray-400 font-bold mt-2">${err.message}</p></div></td></tr>`;
    }
}

async function viewOrder(id) {
    try {
        const res = await fetch('/admin/api/orders/' + id + '?t=' + new Date().getTime());
        if (!res.ok) throw new Error("Order Details Unavailable");
        const order = await res.json();
        
        document.getElementById('modal-order-id').innerText = '#' + id;
        document.getElementById('view-user-name').innerText = order.user_name || 'Guest Member';
        document.getElementById('view-user-email').innerText = order.user_email || 'N/A';
        
        const ship = order.shipping || {};
        document.getElementById('view-shipping-name').innerText = ship.full_name || 'No Name Provided';
        document.getElementById('view-shipping-phone').innerText = ship.phone || 'No Phone';
        document.getElementById('view-shipping-address').innerText = ship.address || 'No Address';
        document.getElementById('view-shipping-loc').innerText = `${ship.city || ''}, ${ship.state || ''} ${ship.zip || ''}`;
        
        const itemList = document.getElementById('view-items');
        itemList.innerHTML = (order.items || []).map(item => `
            <div class="flex items-center justify-between bg-white p-4 rounded-2xl border border-gray-100 shadow-sm">
                <div class="flex items-center">
                    <div class="w-10 h-10 rounded-lg overflow-hidden border border-gray-100 mr-4">
                        <img src="${item.image || 'https://via.placeholder.com/40'}" class="w-full h-full object-cover" onerror="this.src='https://via.placeholder.com/40'">
                    </div>
                    <div class="flex flex-col">
                        <span class="text-xs font-extrabold text-[#0f172a]">${item.name || 'Product'}</span>
                        <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Qty: ${item.quantity || 1}</span>
                    </div>
                </div>
                <span class="text-xs font-black text-[#0f172a]">&#8377;${(item.price || 0) * (item.quantity || 1)}</span>
            </div>
        `).join('');

        document.getElementById('view-total').innerHTML = formatCurrency(order.total || order.total_amount);
        document.getElementById('order-modal').classList.remove('hidden');
    } catch (e) {
        alert('Audit Failure: ' + e.message);
    }
}

function closeModal() {
    document.getElementById('order-modal').classList.add('hidden');
}

async function updateStatus(id, status) {
    try {
        const res = await fetch('/admin/api/orders/' + id + '/status', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });
        const data = await res.json();
        if (data.success) {
            console.log('Fulfillment Synchronized');
        } else {
            throw new Error(data.message || "Sync Failed");
        }
    } catch (e) {
        console.error('Status Sync Error', e);
        alert('Status update failed: ' + e.message);
    }
}

document.addEventListener('DOMContentLoaded', loadOrders);
