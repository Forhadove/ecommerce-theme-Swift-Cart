# SwiftCart - Pure HTML/CSS Template for Python Practice

এই থিমটি **১০০% পিউর HTML5 এবং CSS3** দিয়ে সাজানো হয়েছে। এতে কোনো জাভাস্ক্রিপ্ট (JavaScript) নির্ভরতা রাখা হয়নি, যাতে আপনি পাইথন (Flask বা Django) দিয়ে ব্যাকএন্ডের আসল লজিক নিজে নিজে প্র্যাকটিস করতে পারেন।

---

## 📁 ফাইল ও পেজ পরিচিতি

```
ecommerce-theme/
│
├── index.html            # হোমপেজ (হিরো ব্যানার, ফিচার্স ও ফিচার্ড প্রোডাক্ট কার্ড)
├── products.html         # অল প্রোডাক্ট পেজ (GET মেথডে সার্চ ও ক্যাটাগরি ফিল্টার ফর্ম)
├── product-detail.html   # প্রোডাক্ট ডিটেইলস (পরিমাণ ইনপুট ও POST মেথডে Add to Cart ফর্ম)
├── cart.html             # শピング কার্ট পেজ (টেবিল ডাটা, কোয়ান্টিটি আপডেট, আইটেম ডিলিট ও ক্লিয়ার ফর্ম)
├── checkout.html         # চেকআউট পেজ (গ্রাহকের নাম, ঠিকানা ও পেমেন্ট মেথড সাবমিশন ফর্ম)
├── order-success.html    # অর্ডার কনফার্মেশন ও ইনভয়েস রসিদ
│
└── css/
    └── style.css         # সম্পূর্ণ রেসপনসিভ CSS3 ডিজাইন (Flexbox & CSS Grid)
```

---

## 🐍 পাইথন দিয়ে নিজে করার গাইডলাইন (How to Practice)

### ১. প্রোডাক্ট দেখানো (Jinja2 Loop)
`index.html` ও `products.html`-এ ডামি কার্ডগুলোর জায়গায় আপনার পাইথন ডেটাবেস/লিস্ট লুপ করবেন:
```html
{% for product in products %}
<div class="product-card">
    <img src="{{ product.image }}" alt="{{ product.name }}">
    <h3>{{ product.name }}</h3>
    <p>${{ product.price }}</p>
    
    <form action="/add-to-cart/{{ product.id }}" method="POST">
        <button type="submit" class="btn btn-primary">Add to Cart</button>
    </form>
</div>
{% endfor %}
```

### ২. কার্ট হ্যান্ডলিং (Python Session)
`cart.html`-এ পাইথনের `session['cart']` থেকে আইটেমগুলো লুপ করে টেবিল তৈরি করবেন এবং কোয়ান্টিটি পরিবর্তনের জন্য সাধারণ HTML ফর্ম সাবমিট ব্যবহার করবেন:
```html
{% for item in cart_items %}
<tr>
    <td>{{ item.name }}</td>
    <td>${{ item.price }}</td>
    <td>
        <form action="/cart/update/{{ item.id }}" method="POST">
            <input type="number" name="quantity" value="{{ item.quantity }}">
            <button type="submit">Update</button>
        </form>
    </td>
    <td>
        <form action="/cart/remove/{{ item.id }}" method="POST">
            <button type="submit">Remove</button>
        </form>
    </td>
</tr>
{% endfor %}
```

### ৩. চেকআউট ও অর্ডার সেভ করা (Python Form Handling)
`checkout.html`-এ একটি স্ট্যান্ডার্ড `<form action="/place-order" method="POST">` দেওয়া আছে। পাইথনে ইনপুটগুলো রিসিভ করতে পারবেন:
```python
first_name = request.form['first_name']
email = request.form['email']
address = request.form['address']
payment_method = request.form['payment_method']
```
এরপর ডেটাবেসে অর্ডার সেভ করে ইউজারকে `order-success.html` পেজে রিডাইরেক্ট করে দেবেন।
