/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01531(unsigned int count)
{
    const unsigned int limit = 139u;
    return count > limit ? limit : count;
}
