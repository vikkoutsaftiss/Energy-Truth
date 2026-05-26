using Energy_Truth.Shared.Login;

namespace Energy_Truth_Presentation.Services
{
    public class AuthenticateService : IAuthenticateService
    {
        public User CurrentUser { get; private set; }

        public bool LogIn(User user)
        {
            if (user == null)
            {
                return false;
            }
            CurrentUser = user;
            return true;
        }

        public bool LogOut()
        {
            CurrentUser = null;
            return false;
        }
    }
}
