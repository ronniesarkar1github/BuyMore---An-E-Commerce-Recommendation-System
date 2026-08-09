async function loadProducts() {
    const res = await fetch('/admin/api/products');
    const products = await res.json();
    const list = document.getElementById('product-list');
    list.innerHTML = products.map(p => `
        <tr class="hover:bg-teal-50/10 transition-colors group">
            <td class="px-10 py-6">
                <div class="flex items-center">
                    <div class="w-12 h-12 rounded-2xl overflow-hidden border border-gray-100 shadow-sm mr-5 group-hover:scale-110 transition-transform">
                        <img src="${p.image || 'https://via.placeholder.com/150'}" class="w-full h-full object-cover">
                    </div>
                    <span class="font-bold text-[#0f172a] text-sm">${p.name}</span>
                </div>
            </td>
            <td class="px-10 py-6 text-[10px] font-black text-gray-400 uppercase tracking-widest">${p.category}</td>
            <td class="px-10 py-6 text-right font-black text-[#0f172a] text-sm">&#8377;${p.price}</td>
            <td class="px-10 py-6 text-right">
                <span class="px-3 py-1 ${p.stock > 10 ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'} text-[10px] font-black rounded-full uppercase tracking-tighter">
                    ${p.stock} Units
                </span>
            </td>
            <td class="px-10 py-6 text-center">
                <div class="flex items-center justify-center space-x-2">
                    <button onclick="editProduct('${p._id}', '${(p.name || '').replace(/'/g, "\\'")}', '${p.price}', '${(p.category || '').replace(/'/g, "\\'")}', '${p.stock}', '${(p.description || '').replace(/'/g, "\\'")}', '${(p.image || '').replace(/'/g, "\\'")}')" class="w-9 h-9 flex items-center justify-center rounded-full bg-teal-50 text-teal-600 hover:bg-teal-600 hover:text-white transition-all">
                        <i class="fas fa-pen-nib text-xs"></i>
                    </button>
                    <button onclick="deleteProduct('${p._id}')" class="w-9 h-9 flex items-center justify-center rounded-full bg-red-50 text-red-500 hover:bg-red-500 hover:text-white transition-all">
                        <i class="fas fa-trash-alt text-xs"></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

function openModal() {
    document.getElementById('productForm').reset();
    document.getElementById('edit-id').value = '';
    document.getElementById('modal-title').innerText = 'Provision Product';
    document.getElementById('product-modal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('product-modal').classList.add('hidden');
}

function editProduct(id, name, price, category, stock, description, image) {
    document.getElementById('edit-id').value = id;
    document.getElementById('name').value = name;
    document.getElementById('price').value = price;
    document.getElementById('category').value = category;
    document.getElementById('stock').value = stock;
    document.getElementById('description').value = description;
    document.getElementById('image').value = image || '';
    document.getElementById('modal-title').innerText = 'Modify Provision';
    document.getElementById('product-modal').classList.remove('hidden');
}

document.getElementById('productForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('edit-id').value;
    const payload = {
        name: document.getElementById('name').value,
        price: document.getElementById('price').value,
        category: document.getElementById('category').value,
        stock: document.getElementById('stock').value,
        description: document.getElementById('description').value,
        image: document.getElementById('image').value
    };

    const res = await fetch('/admin/api/products' + (id ? '/' + id : ''), {
        method: id ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    if ((await res.json()).success) {
        closeModal();
        loadProducts();
    }
});

async function deleteProduct(id) {
    if (!confirm('Execute deletion of this product entry?')) return;
    const res = await fetch('/admin/api/products/' + id, { method: 'DELETE' });
    if ((await res.json()).success) loadProducts();
}

document.addEventListener('DOMContentLoaded', loadProducts);
