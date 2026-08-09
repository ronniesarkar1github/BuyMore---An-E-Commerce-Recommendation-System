let currentPaymentId = null;

async function loadPayments() {
    const res = await fetch('/admin/api/payments');
    const payments = await res.json();
    const list = document.getElementById('payment-list');
    list.innerHTML = payments.length ? payments.map(p => `
        <tr class="hover:bg-teal-50/10 transition-colors group">
            <td class="px-10 py-6 font-mono text-xs font-bold text-gray-400 group-hover:text-teal-600 transition-colors">#${p._id.slice(-6).toUpperCase()}</td>
            <td class="px-10 py-6 font-mono text-xs text-gray-400">#${p.order_id.slice(-6).toUpperCase() || 'N/A'}</td>
            <td class="px-10 py-6">
                <span class="font-extrabold text-[#0f172a] text-sm">${p.user_email || 'N/A'}</span>
            </td>
            <td class="px-10 py-6">
                <span class="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em]">${p.method || 'CARD'}</span>
            </td>
            <td class="px-10 py-6 text-right font-black text-[#0f172a] text-sm">&#8377;${p.amount || 0}</td>
            <td class="px-10 py-6 text-center">
                <div class="flex items-center justify-center space-x-3">
                    <span class="px-4 py-1.5 ${p['payment-status'] === 'Pending' ? 'bg-amber-50 text-amber-600 border-amber-100' : 'bg-green-50 text-green-600 border-green-100'} text-[9px] font-black rounded-full uppercase tracking-widest border">
                        ${p['payment-status'] || 'Paid'}
                    </span>
                    ${p['payment-status'] === 'Pending' ? `<button onclick="window.confirmPayment('${p._id}')" class="text-green-500 hover:text-green-700 transition-colors" title="Mark as Paid"><i class="fas fa-check-circle text-lg drop-shadow"></i></button>` : `<span class="w-[18px]"></span>`}
                </div>
            </td>
        </tr>
    `).join('') : `<tr><td colspan="6" class="px-10 py-12 text-center text-xs font-bold text-gray-300 uppercase tracking-widest">No Settlements Found</td></tr>`;
}

window.confirmPayment = function(id) {
    currentPaymentId = id;
    document.getElementById('payment-modal').classList.remove('hidden');
};

function closePaymentModal() {
    currentPaymentId = null;
    document.getElementById('payment-modal').classList.add('hidden');
}

// Event Listeners for Custom Modal
document.addEventListener('DOMContentLoaded', () => {
    loadPayments();
    
    const confirmBtn = document.getElementById('confirm-yes');
    const cancelBtn = document.getElementById('confirm-no');
    
    if (confirmBtn) {
        confirmBtn.onclick = async function() {
            if (!currentPaymentId) return;
            
            confirmBtn.disabled = true;
            confirmBtn.textContent = "Processing...";
            
            try {
                const res = await fetch('/admin/api/payments/' + currentPaymentId + '/status', {
                    method: 'PATCH',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({status: 'Paid'})
                });
                
                if ((await res.json()).success) {
                    closePaymentModal();
                    loadPayments();
                }
            } catch (err) {
                console.error("Payment settlement failed:", err);
            } finally {
                confirmBtn.disabled = false;
                confirmBtn.textContent = "Yes, Mark as Paid";
            }
        };
    }
    
    if (cancelBtn) {
        cancelBtn.onclick = closePaymentModal;
    }
    
    // Close on backdrop click
    const modal = document.getElementById('payment-modal');
    if (modal) {
        modal.onclick = function(e) {
            if (e.target === modal) closePaymentModal();
        };
    }
});
