# knowledge_base.py
# This file serves as the raw, unstructured document knowledge base for the BuyMore chatbot RAG engine.

FAQ_POLICIES = [
    {
        "id": "doc_returns_1",
        "title": "Standard Return Policy",
        "text": "You can return most items purchased from BuyMore within 14 days of delivery for a full refund. Items must be in their original condition and packaging. Electronic items must be completely unopened."
    },
    {
        "id": "doc_returns_2",
        "title": "Damaged or Defective Items",
        "text": "If you receive a defective or damaged product, please contact support within 48 hours of delivery. We will arrange a free replacement or full refund, including shipping costs. Please provide photos of the damaged item."
    },
    {
        "id": "doc_shipping_1",
        "title": "Standard Shipping",
        "text": "Standard shipping usually takes 3 to 5 business days and incurs a flat rate of $5.99. Free shipping is automatically applied to all orders with a total cart value exceeding $100."
    },
    {
        "id": "doc_shipping_2",
        "title": "Expedited Shipping Options",
        "text": "We offer next-day delivery for a flat fee of $15.99. Orders for next-day delivery must be placed before 2:00 PM local time. Next-day delivery is not available for large furniture items."
    },
    {
        "id": "doc_refunds_1",
        "title": "Refund Processing Time",
        "text": "Once we receive your returned item, it typically takes 2 to 3 business days to inspect it. After inspection, the refund will be initiated to your original payment method, which may take another 3 to 5 business days to reflect in your banking account."
    },
    {
        "id": "doc_refunds_2",
        "title": "Non-refundable Items",
        "text": "Certain items are strictly non-refundable and cannot be returned. These include digital gift cards, personalized or custom-made products, opened software, and clearance items marked as 'Final Sale'."
    },
    {
        "id": "doc_warranty_1",
        "title": "Electronics Warranty",
        "text": "All electronic devices purchased from BuyMore come with a standard 1-year manufacturer warranty covering internal hardware defects. This warranty does not cover accidental damage, drops, or water damage."
    },
    {
        "id": "doc_payment_1",
        "title": "Payment Methods Accepted",
        "text": "We accept major credit cards (Visa, MasterCard, Amex), Debit Cards, UPI, and Digital Wallets. We currently do not support Cash on Delivery (COD) for orders outside major metropolitan areas or for total amounts exceeding INR 20,000."
    },
    {
        "id": "doc_account_1",
        "title": "Deleting your account",
        "text": "You can delete your account by navigating to the Account section and clicking on 'Delete Data'. Note that deleting your account will permanently erase your order history and wishlist."
    },
    {
        "id": "doc_trending_deals",
        "title": "Trending Products and Daily Deals",
        "text": "Our trending products for today feature exclusive flash deals across electronics, fashion, and home appliances. These items are selected based on popularity and maximum savings. Check out our top picks below:"
    }
]
