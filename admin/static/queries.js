async function loadQueries() {
    const res = await fetch('/admin/api/queries');
    const queries = await res.json();
    const list = document.getElementById('query-list');
    list.innerHTML = queries.length ? queries.map(q => `
        <tr class="hover:bg-teal-50/10 transition-colors group">
            <td class="px-10 py-6">
                <span class="font-extrabold text-[#0f172a] text-sm">${q.name || 'Anonymous'}</span>
            </td>
            <td class="px-10 py-6">
                <span class="text-xs font-bold text-gray-500">${q.email || 'N/A'}</span>
            </td>
            <td class="px-10 py-6">
                <span class="text-xs font-bold text-gray-500">${q.phone || 'N/A'}</span>
            </td>
            <td class="px-10 py-6">
                <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">${q.topic || 'N/A'}</span>
            </td>
            <td class="px-10 py-6 text-center">
                <p class="text-xs font-semibold text-gray-500 truncate max-w-[150px] mx-auto">${q.message || ''}</p>
            </td>
            <td class="px-10 py-6 text-center">
                <span class="text-[10px] font-bold text-gray-400 tracking-widest">${q.created_at || 'N/A'}</span>
            </td>
            <td class="px-10 py-6 text-center">
                <span class="px-4 py-1.5 text-[9px] font-black rounded-full uppercase tracking-widest border
                    ${(q.status === 'Completed') ? 'bg-green-50 text-green-600 border-green-100' : 
                      (q.status === 'Declined') ? 'bg-red-50 text-red-600 border-red-100' : 
                      'bg-amber-50 text-amber-600 border-amber-100'}">
                    ${q.status || 'Pending'}
                </span>
            </td>
            <td class="px-10 py-6 text-center">
                <div class="flex items-center justify-center space-x-2">
                    <button 
                        ${(q.status === 'Completed' || q.status === 'Declined') ? 'disabled' : ''} 
                        onclick="updateQueryStatus('${q._id}', 'Completed')" 
                        class="px-4 py-2 ${q.status === 'Completed' || q.status === 'Declined' ? 'bg-gray-300 cursor-not-allowed' : 'bg-green-500 hover:bg-green-600 active:scale-95'} text-white text-[9px] font-bold uppercase tracking-widest rounded shadow-sm transition-all">
                        Resolved
                    </button>
                    <button 
                        ${(q.status === 'Completed' || q.status === 'Declined') ? 'disabled' : ''} 
                        onclick="updateQueryStatus('${q._id}', 'Declined')" 
                        class="px-4 py-2 ${q.status === 'Completed' || q.status === 'Declined' ? 'bg-gray-300 cursor-not-allowed' : 'bg-red-500 hover:bg-red-600 active:scale-95'} text-white text-[9px] font-bold uppercase tracking-widest rounded shadow-sm transition-all">
                        Rejected
                    </button>
                </div>
            </td>
        </tr>
    `).join('') : `<tr><td colspan="8" class="px-10 py-12 text-center text-xs font-bold text-gray-300 uppercase tracking-widest">No Active Reports</td></tr>`;
}

function openQuery(id, msg, resp) {
    document.getElementById('query-id').value = id;
    document.getElementById('view-message').innerText = msg;
    document.getElementById('admin-response').value = resp;
    document.getElementById('query-modal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('query-modal').classList.add('hidden');
}

async function updateQueryStatus(id, status) {
    const res = await fetch('/admin/api/queries/' + id + '/status', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: status, response: '' })
    });
    const data = await res.json();
    if (data.success) {
        loadQueries();
    }
}

document.addEventListener('DOMContentLoaded', loadQueries);
