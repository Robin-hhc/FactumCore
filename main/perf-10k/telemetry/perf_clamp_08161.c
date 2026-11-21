/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08161(unsigned int count)
{
    const unsigned int limit = 52u;
    return count > limit ? limit : count;
}
