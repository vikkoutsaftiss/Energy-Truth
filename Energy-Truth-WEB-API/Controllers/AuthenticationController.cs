using Energy_Truth.Shared.Login;
using Microsoft.AspNetCore.Mvc;

namespace Energy_Truth_WEB_API.Controllers
{
    [ApiController]
    [Route("api/[controller]")] // Dit zorgt dat de URL /api/authentication wordt
    public class AuthenticationController : Controller
    {
        [HttpPost("login")] // wanneer de post actie login uitgevoerd wordt wordt deze methode aangeroepen.
        public IActionResult Login([FromBody] LoginRequest request)
        {
            if (request == null)
            {
                return BadRequest("Ongeldige aanvraag.");
            }

            if (request.Username == "admin" && request.Password == "password")
            {
                return Ok(request);
            }

            return Unauthorized();
        }
    }

    }
