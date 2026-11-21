/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08022(unsigned int count)
{
    const unsigned int limit = 179u;
    return count > limit ? limit : count;
}
