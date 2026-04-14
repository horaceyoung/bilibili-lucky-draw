# Bilibili Lucky Draw / B站抽奖工具

从B站动态或视频的互动用户中随机抽取中奖者。

## 支持的输入

| 类型 | 格式 |
|------|------|
| 动态 | `https://t.bilibili.com/123456` |
| 动态 | `https://www.bilibili.com/opus/123456` |
| 视频 | `https://www.bilibili.com/video/BVxxxxxxx` |
| 视频 | `https://www.bilibili.com/video/av123456` |
| 纯 BV 号 | `BV17x411w7KC` |
| 纯动态 ID | `1183984804064919575` |

## 支持的抽奖条件

| 条件 | 动态 | 视频 | 需要 SESSDATA |
|------|:----:|:----:|:------------:|
| 评论 | ✅ | ✅ | 否 |
| 转发 | ✅ | - | 是 |
| 点赞 | ✅ | - | 是 |
| 仅关注用户 | ✅ | ✅ | 是 |

条件可任意组合，用户需同时满足所有勾选条件才能参与抽奖。

## 使用方法

```bash
# 1. 启动本地服务器
python server.py

# 2. 浏览器打开
open http://localhost:8080
```

无需安装任何第三方依赖，仅使用 Python 标准库。

## 获取 SESSDATA

转发、点赞、关注验证功能需要 SESSDATA：

1. 浏览器登录 [bilibili.com](https://www.bilibili.com)
2. 按 `F12`（Mac: `Cmd+Option+I`）打开开发者工具
3. 切换到 **Application** 标签
4. 左侧 **Cookies** → `https://www.bilibili.com`
5. 找到 `SESSDATA`，复制其 Value

> **注意：** SESSDATA 等同于登录凭证，请勿分享给他人。

## 其他功能

- 自动排除动态/视频作者
- 手动屏蔽 UID 名单
- 抽奖滚动动画
- 支持一次抽取多人
- 导出参与者名单 / 获奖名单（CSV）

## 原理

浏览器无法直接调用B站 API（CORS 限制），`server.py` 作为本地代理转发请求。所有数据处理在本地完成，不经过任何第三方服务器。
