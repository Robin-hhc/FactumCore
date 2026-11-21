/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06554(unsigned int count)
{
    const unsigned int limit = 123u;
    return count > limit ? limit : count;
}
