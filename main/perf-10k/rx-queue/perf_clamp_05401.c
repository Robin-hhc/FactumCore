/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05401(unsigned int count)
{
    const unsigned int limit = 193u;
    return count > limit ? limit : count;
}
