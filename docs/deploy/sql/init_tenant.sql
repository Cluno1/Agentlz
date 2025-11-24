-- Active: 1763784767296@@117.72.162.89@13306@agentlz
SET NAMES utf8mb4;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `tenant`;

-- 租户表：用于多租户隔离与管理
-- 说明：
--  - `id` 为租户唯一标识，作为主键；建议使用 UUID 或默认值 `default`
--  - `name` 为租户展示名称，唯一约束保证名称不可重复
--  - `disabled` 控制租户启用状态（0 否，1 是），可用于快速停用租户
--  - `created_at`/`updated_at` 记录创建与更新时间，便于审计
CREATE TABLE `tenant` (
    `id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'default' COMMENT '租户唯一ID（主键，建议 UUID 或 default）',
    `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '租户名称（唯一）',
    `disabled` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否禁用租户：0否 1是',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`) USING BTREE,
    UNIQUE INDEX `uk_tenant_name` (`name`) USING BTREE, -- 名称唯一索引，加速按名称查找
    INDEX `idx_tenant_disabled` (`disabled`) USING BTREE -- 状态筛选索引，便于管理面列表过滤
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

DROP TABLE IF EXISTS `document`;

-- 文档表：存储各租户的文档元数据与正文
-- 说明：
--  - 通过 `tenant_id` 与上游业务实现租户隔离；查询务必携带租户条件
--  - 文本字段较多，`content` 使用 longtext 以存储大体量内容；生产环境可考虑外部存储
--  - 常用筛选维度：状态、上传人、租户；相应建立索引以优化查询性能
CREATE TABLE `document` (
    `id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'default' COMMENT '文档唯一ID（主键，建议 UUID 或 default）',
    `tenant_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '租户ID（多租户隔离）',
    `uploaded_by_user_id` bigint(20) UNSIGNED NULL DEFAULT NULL COMMENT '上传者用户ID（可为空）',
    `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '文档状态（如 draft/published 等）',
    `upload_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文档标题',
    `content` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL COMMENT '文档正文（长文本）',
    `disabled` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否禁用文档：0否 1是',
    `type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '文档类型',
    `tags` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '标签（逗号分隔或 JSON）',
    `description` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL COMMENT '摘要/描述',
    `mata_https` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '元数据链接（如预览地址）',
    `save_https` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '存储地址（如附件/对象存储路径）',
    PRIMARY KEY (`id`) USING BTREE,
    INDEX `idx_document_tenant` (`tenant_id`) USING BTREE, -- 按租户过滤加速
    INDEX `idx_document_uploader` (`uploaded_by_user_id`) USING BTREE, -- 上传人筛选加速
    INDEX `idx_document_status` (`tenant_id`, `status`) USING BTREE -- 租户+状态组合索引，提高状态筛选性能
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

DROP TABLE IF EXISTS `user_doc_permission`;

-- 用户-文档权限关系表：定义用户对文档的访问/操作权限
-- 说明：
--  - 通过唯一约束 `user_id + doc_id` 保证同一用户对同一文档只有一条权限记录
--  - `perm` 使用枚举，限制可选权限值，避免非法输入
CREATE TABLE `user_doc_permission` (
    `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `user_id` bigint(20) UNSIGNED NOT NULL COMMENT '用户ID',
    `doc_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文档ID',
    `perm` enum(
        'admin',
        'read',
        'write',
        'none'
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'read' COMMENT '权限枚举（admin/read/write/none）',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`) USING BTREE,
    UNIQUE INDEX `uk_user_doc` (`user_id`, `doc_id`) USING BTREE, -- 唯一键，避免重复授权
    INDEX `idx_perm_user` (`user_id`) USING BTREE, -- 按用户过滤加速
    INDEX `idx_perm_doc` (`doc_id`) USING BTREE -- 按文档过滤加速
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;