export type MockUser = {
  id: string;
  // 用户名/账号
  username: string;
  email?: string;
  password?: string;
  fullName?: string;
  avatar?: string;
  // 角色
  role?: RoleType;
  disabled?: boolean;
  // 创建时间
  createdAt?: string;
  // 创建人ID,如果为空则是系统默认创建或者自己注册
  createdById?: string;
};