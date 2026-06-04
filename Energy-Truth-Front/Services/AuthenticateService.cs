using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Login;

namespace Energy_Truth_Presentation.Services
{
    public class AuthenticateService : IAuthenticateService
    {
        public LoggedInUser CurrentUser { get; private set; }
        public CustomBatteryDTO? CustomBattery { get; set; }

        public bool LogIn(LoggedInUser user)
        {
            if (user == null)
            {
                return false;
            }
            CurrentUser = user;
            return true;
        }

        public void LogOut()
        {
            CurrentUser = null;
        }
    }
}
