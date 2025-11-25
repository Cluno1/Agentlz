
SET NAMES utf8mb4;

SET FOREIGN_KEY_CHECKS = 0;

-- 操作日志表：记录对租户（tenant）的增删改及相关操作
DROP TABLE IF EXISTS `tenant_operation_log`;
CREATE TABLE `tenant_operation_log` (
    `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `tenant_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '租户ID',
    `operator_user_id` bigint(20) UNSIGNED NULL DEFAULT NULL COMMENT '操作者用户ID（来自会话变量 @actor_user_id）',
    `operation` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '操作类型（如 tenant_create/tenant_update_name 等）',
    `before_value` json NULL COMMENT '变更前快照（JSON）',
    `after_value` json NULL COMMENT '变更后快照（JSON）',
    `ip` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '操作者IP（@actor_ip）',
    `trace_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '链路追踪ID（@actor_trace_id）',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
    PRIMARY KEY (`id`) USING BTREE,
    INDEX `idx_tenant_op` (`tenant_id`, `operation`) USING BTREE,
    INDEX `idx_operator_user` (`operator_user_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- 触发器：记录租户新增/更新/删除
DELIMITER $$
DROP TRIGGER IF EXISTS `tenant_ai` $$
CREATE TRIGGER `tenant_ai` AFTER INSERT ON `tenant` FOR EACH ROW
BEGIN
  INSERT INTO tenant_operation_log(
      tenant_id, operator_user_id, operation, before_value, after_value, ip, trace_id
  )
  VALUES (
      NEW.id,
      COALESCE(@actor_user_id, NULL),
      'tenant_create',
      NULL,
      JSON_OBJECT('name', NEW.name, 'disabled', NEW.disabled),
      COALESCE(@actor_ip, NULL),
      COALESCE(@actor_trace_id, NULL)
  );
END $$

DROP TRIGGER IF EXISTS `tenant_au` $$
CREATE TRIGGER `tenant_au` AFTER UPDATE ON `tenant` FOR EACH ROW
BEGIN
  -- 名称变更
  IF (OLD.name <> NEW.name) THEN
    INSERT INTO tenant_operation_log(tenant_id, operator_user_id, operation, before_value, after_value, ip, trace_id)
    VALUES (
      NEW.id,
      COALESCE(@actor_user_id, NULL),
      'tenant_update_name',
      JSON_OBJECT('name', OLD.name),
      JSON_OBJECT('name', NEW.name),
      COALESCE(@actor_ip, NULL),
      COALESCE(@actor_trace_id, NULL)
    );
  END IF;
  -- 启用状态变更
  IF (OLD.disabled <> NEW.disabled) THEN
    INSERT INTO tenant_operation_log(tenant_id, operator_user_id, operation, before_value, after_value, ip, trace_id)
    VALUES (
      NEW.id,
      COALESCE(@actor_user_id, NULL),
      'tenant_update_disabled',
      JSON_OBJECT('disabled', OLD.disabled),
      JSON_OBJECT('disabled', NEW.disabled),
      COALESCE(@actor_ip, NULL),
      COALESCE(@actor_trace_id, NULL)
    );
  END IF;
END $$

DROP TRIGGER IF EXISTS `tenant_ad` $$
CREATE TRIGGER `tenant_ad` AFTER DELETE ON `tenant` FOR EACH ROW
BEGIN
  INSERT INTO tenant_operation_log(tenant_id, operator_user_id, operation, before_value, after_value, ip, trace_id)
  VALUES (
    OLD.id,
    COALESCE(@actor_user_id, NULL),
    'tenant_delete',
    JSON_OBJECT('name', OLD.name, 'disabled', OLD.disabled),
    NULL,
    COALESCE(@actor_ip, NULL),
    COALESCE(@actor_trace_id, NULL)
  );
END $$
DELIMITER ;


DROP TABLE IF EXISTS `user_operation_log`;
CREATE TABLE `user_operation_log` (
    `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    `tenant_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '所属租户ID（用户操作必然属于某租户）',
    `user_id` bigint(20) UNSIGNED NOT NULL COMMENT '被操作的用户ID',
    `operator_user_id` bigint(20) UNSIGNED NULL DEFAULT NULL COMMENT '操作者用户ID（@actor_user_id）',
    `operation` varchar(64) NOT NULL COMMENT '操作类型，如 user_create / user_update_role / user_delete 等',
    `before_value` json NULL COMMENT '变更前快照',
    `after_value` json NULL COMMENT '变更后快照',
    `ip` varchar(64) NULL DEFAULT NULL COMMENT '操作者IP（@actor_ip）',
    `trace_id` varchar(128) NULL DEFAULT NULL COMMENT '链路追踪ID（@actor_trace_id）',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作发生时间',
    PRIMARY KEY (`id`),
    INDEX `idx_user_op_user` (`user_id`),
    INDEX `idx_user_op_tenant` (`tenant_id`, `operation`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DELIMITER $$

DROP TRIGGER IF EXISTS `users_ai` $$
CREATE TRIGGER `users_ai`
AFTER INSERT ON `users`
FOR EACH ROW
BEGIN
  INSERT INTO user_operation_log(
    tenant_id,
    user_id,
    operator_user_id,
    operation,
    before_value,
    after_value,
    ip,
    trace_id
  )
  VALUES (
    NEW.tenant_id,
    NEW.id,
    COALESCE(@actor_user_id, NULL),
    'user_create',
    NULL,
    JSON_OBJECT(
        'username', NEW.username,
        'email', NEW.email,
        'role', NEW.role,
        'tenant_id', NEW.tenant_id,
        'disabled', NEW.disabled
    ),
    COALESCE(@actor_ip, NULL),
    COALESCE(@actor_trace_id, NULL)
  );
END $$

DELIMITER ;

DELIMITER $$

DROP TRIGGER IF EXISTS `users_au` $$
CREATE TRIGGER `users_au`
AFTER UPDATE ON `users`
FOR EACH ROW
BEGIN

  -- 用户名变化
  IF (OLD.username <> NEW.username) THEN
    INSERT INTO user_operation_log(tenant_id, user_id, operator_user_id, operation, before_value, after_value, ip, trace_id)
    VALUES (
      NEW.tenant_id,
      NEW.id,
      COALESCE(@actor_user_id, NULL),
      'user_update_username',
      JSON_OBJECT('username', OLD.username),
      JSON_OBJECT('username', NEW.username),
      COALESCE(@actor_ip, NULL),
      COALESCE(@actor_trace_id, NULL)
    );
  END IF;

  -- 邮箱变化
  IF (OLD.email <> NEW.email) THEN
    INSERT INTO user_operation_log(tenant_id, user_id, operator_user_id, operation, before_value, after_value, ip, trace_id)
    VALUES (
      NEW.tenant_id,
      NEW.id,
      COALESCE(@actor_user_id, NULL),
      'user_update_email',
      JSON_OBJECT('email', OLD.email),
      JSON_OBJECT('email', NEW.email),
      COALESCE(@actor_ip, NULL),
      COALESCE(@actor_trace_id, NULL)
    );
  END IF;

  -- 角色变化
  IF (OLD.role <> NEW.role) THEN
    INSERT INTO user_operation_log(tenant_id, user_id, operator_user_id, operation, before_value, after_value, ip, trace_id)
    VALUES (
      NEW.tenant_id,
      NEW.id,
      COALESCE(@actor_user_id, NULL),
      'user_update_role',
      JSON_OBJECT('role', OLD.role),
      JSON_OBJECT('role', NEW.role),
      COALESCE(@actor_ip, NULL),
      COALESCE(@actor_trace_id, NULL)
    );
  END IF;

  -- 禁用状态变化
  IF (OLD.disabled <> NEW.disabled) THEN
    INSERT INTO user_operation_log(tenant_id, user_id, operator_user_id, operation, before_value, after_value, ip, trace_id)
    VALUES (
      NEW.tenant_id,
      NEW.id,
      COALESCE(@actor_user_id, NULL),
      'user_update_disabled',
      JSON_OBJECT('disabled', OLD.disabled),
      JSON_OBJECT('disabled', NEW.disabled),
      COALESCE(@actor_ip, NULL),
      COALESCE(@actor_trace_id, NULL)
    );
  END IF;

  -- 租户 ID 变化（可能发生“跨租户转移”）
  IF (OLD.tenant_id <> NEW.tenant_id) THEN
    INSERT INTO user_operation_log(tenant_id, user_id, operator_user_id, operation, before_value, after_value, ip, trace_id)
    VALUES (
      NEW.tenant_id,
      NEW.id,
      COALESCE(@actor_user_id, NULL),
      'user_update_tenant',
      JSON_OBJECT('tenant_id', OLD.tenant_id),
      JSON_OBJECT('tenant_id', NEW.tenant_id),
      COALESCE(@actor_ip, NULL),
      COALESCE(@actor_trace_id, NULL)
    );
  END IF;

END $$

DELIMITER ;

DELIMITER $$

DROP TRIGGER IF EXISTS `users_ad` $$
CREATE TRIGGER `users_ad`
AFTER DELETE ON `users`
FOR EACH ROW
BEGIN
  INSERT INTO user_operation_log(
    tenant_id,
    user_id,
    operator_user_id,
    operation,
    before_value,
    after_value,
    ip,
    trace_id
  )
  VALUES (
    OLD.tenant_id,
    OLD.id,
    COALESCE(@actor_user_id, NULL),
    'user_delete',
    JSON_OBJECT(
        'username', OLD.username,
        'email', OLD.email,
        'role', OLD.role,
        'tenant_id', OLD.tenant_id,
        'disabled', OLD.disabled
    ),
    NULL,
    COALESCE(@actor_ip, NULL),
    COALESCE(@actor_trace_id, NULL)
  );
END $$

DELIMITER ;

-- 文档操作日志表：记录文档的创建、删除操作
DROP TABLE IF EXISTS `document_operation_log`;
CREATE TABLE `document_operation_log` (
    `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    `tenant_id` varchar(64) NOT NULL COMMENT '文档所属租户',
    `doc_id` varchar(64) NOT NULL COMMENT '文档ID',
    `operator_user_id` bigint(20) UNSIGNED NULL DEFAULT NULL COMMENT '操作者ID',
    `operation` varchar(64) NOT NULL COMMENT '操作类型：document_create/document_delete',
    `before_value` json NULL COMMENT '变更前快照',
    `after_value` json NULL COMMENT '变更后快照',
    `ip` varchar(64) NULL DEFAULT NULL COMMENT '操作者IP',
    `trace_id` varchar(128) NULL DEFAULT NULL COMMENT '链路ID',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
    PRIMARY KEY (`id`),
    INDEX `idx_doc_op` (`tenant_id`, `doc_id`, `operation`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DELIMITER $$

DROP TRIGGER IF EXISTS `document_ai` $$
CREATE TRIGGER `document_ai`
AFTER INSERT ON `document`
FOR EACH ROW
BEGIN
  INSERT INTO document_operation_log(
      tenant_id,
      doc_id,
      operator_user_id,
      operation,
      before_value,
      after_value,
      ip,
      trace_id
  )
  VALUES (
      NEW.tenant_id,
      NEW.id,
      COALESCE(@actor_user_id, NULL),
      'document_create',
      NULL,
      JSON_OBJECT(
          'title', NEW.title,
          'status', NEW.status,
          'uploaded_by_user_id', NEW.uploaded_by_user_id,
          'disabled', NEW.disabled
      ),
      COALESCE(@actor_ip, NULL),
      COALESCE(@actor_trace_id, NULL)
  );
END $$

DELIMITER ;
DELIMITER $$

DROP TRIGGER IF EXISTS `document_ad` $$
CREATE TRIGGER `document_ad`
AFTER DELETE ON `document`
FOR EACH ROW
BEGIN
  INSERT INTO document_operation_log(
      tenant_id,
      doc_id,
      operator_user_id,
      operation,
      before_value,
      after_value,
      ip,
      trace_id
  )
  VALUES (
      OLD.tenant_id,
      OLD.id,
      COALESCE(@actor_user_id, NULL),
      'document_delete',
      JSON_OBJECT(
          'title', OLD.title,
          'status', OLD.status,
          'uploaded_by_user_id', OLD.uploaded_by_user_id,
          'disabled', OLD.disabled
      ),
      NULL,
      COALESCE(@actor_ip, NULL),
      COALESCE(@actor_trace_id, NULL)
  );
END $$

DELIMITER ;

-- 用户文档权限操作日志表：记录用户对文档的权限变更操作

DROP TABLE IF EXISTS `user_doc_permission_log`;
CREATE TABLE `user_doc_permission_log` (
    `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    `tenant_id` varchar(64) NOT NULL COMMENT '文档所属租户（通过 doc → tenant 推断）',
    `doc_id` varchar(64) NOT NULL COMMENT '文档ID',
    `user_id` bigint(20) UNSIGNED NOT NULL COMMENT '被授予权限的用户',
    `operator_user_id` bigint(20) UNSIGNED NULL DEFAULT NULL COMMENT '操作人',
    `operation` varchar(64) NOT NULL COMMENT '操作类型：perm_create/perm_update/perm_delete',
    `before_value` json NULL,
    `after_value` json NULL,
    `ip` varchar(64) NULL DEFAULT NULL,
    `trace_id` varchar(128) NULL DEFAULT NULL,
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `idx_perm_log` (`tenant_id`, `doc_id`, `user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DELIMITER $$

DROP TRIGGER IF EXISTS `user_doc_permission_ai` $$
CREATE TRIGGER `user_doc_permission_ai`
AFTER INSERT ON user_doc_permission
FOR EACH ROW
BEGIN
  DECLARE docTenant VARCHAR(64);

  SELECT tenant_id INTO docTenant FROM document WHERE id = NEW.doc_id LIMIT 1;

  INSERT INTO user_doc_permission_log(
      tenant_id,
      doc_id,
      user_id,
      operator_user_id,
      operation,
      before_value,
      after_value,
      ip,
      trace_id
  ) VALUES (
      docTenant,
      NEW.doc_id,
      NEW.user_id,
      COALESCE(@actor_user_id, NULL),
      'perm_create',
      NULL,
      JSON_OBJECT('perm', NEW.perm),
      COALESCE(@actor_ip, NULL),
      COALESCE(@actor_trace_id, NULL)
  );
END $$

DELIMITER ;

DELIMITER $$

DROP TRIGGER IF EXISTS `user_doc_permission_au` $$
CREATE TRIGGER `user_doc_permission_au`
AFTER UPDATE ON user_doc_permission
FOR EACH ROW
BEGIN
  DECLARE docTenant VARCHAR(64);

  IF (OLD.perm <> NEW.perm) THEN

    SELECT tenant_id INTO docTenant FROM document WHERE id = NEW.doc_id LIMIT 1;

    INSERT INTO user_doc_permission_log(
        tenant_id,
        doc_id,
        user_id,
        operator_user_id,
        operation,
        before_value,
        after_value,
        ip,
        trace_id
    ) VALUES (
        docTenant,
        NEW.doc_id,
        NEW.user_id,
        COALESCE(@actor_user_id, NULL),
        'perm_update',
        JSON_OBJECT('perm', OLD.perm),
        JSON_OBJECT('perm', NEW.perm),
        COALESCE(@actor_ip, NULL),
        COALESCE(@actor_trace_id, NULL)
    );

  END IF;

END $$

DELIMITER ;

DELIMITER $$

DROP TRIGGER IF EXISTS `user_doc_permission_ad` $$
CREATE TRIGGER `user_doc_permission_ad`
AFTER DELETE ON user_doc_permission
FOR EACH ROW
BEGIN
  DECLARE docTenant VARCHAR(64);

  SELECT tenant_id INTO docTenant FROM document WHERE id = OLD.doc_id LIMIT 1;

  INSERT INTO user_doc_permission_log(
      tenant_id,
      doc_id,
      user_id,
      operator_user_id,
      operation,
      before_value,
      after_value,
      ip,
      trace_id
  ) VALUES (
      docTenant,
      OLD.doc_id,
      OLD.user_id,
      COALESCE(@actor_user_id, NULL),
      'perm_delete',
      JSON_OBJECT('perm', OLD.perm),
      NULL,
      COALESCE(@actor_ip, NULL),
      COALESCE(@actor_trace_id, NULL)
  );
END $$

DELIMITER ;

SET FOREIGN_KEY_CHECKS = 1;