# 京东电商 ClickHouse 数据库表结构

> 表名中的 `1000000266` 是店铺 ID（shopId），实际使用时按需替换。

---

## 表关联关系

```
jd_{shopId}_wares (商品表)
    │
    ├── wareId ←→ sku_id (jd_{shopId}_comments.sku_id = wares.wareId)
    │   一个商品有多条评论
    │
    └── toString(wareId) ←→ item_id (jd_{shopId}_qa.item_id = toString(wares.wareId))
        一个商品有多条问答

jd_{shopId}_comments (评论表)
    │
    └── sku_id ←→ item_id (toString(comments.sku_id) = qa.item_id)
        评论和问答通过商品ID关联

jd_{shopId}_qa (问答表)
    每行存储一条回答，问题信息冗余存储（同一 question_id 多行 = 多个回答）
```

---