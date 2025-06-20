INSERT OR REPLACE INTO subscriptions (
    user_id,
    subscription_active,
    requests_left,
    tariff,
    search_requests_left,
    outfit_analysis_left,
    advice_messages_left
) VALUES (
    7822350282,
    1,          -- subscription_active=True
    10000,        -- Общие запросы
    'month',    -- Тариф на месяц
    500,         -- Поиск одежды
    200,         -- Анализ фото
    1000         -- Сообщения в диалоге
);
