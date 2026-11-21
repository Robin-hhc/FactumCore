/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07938(unsigned int count)
{
    const unsigned int limit = 245u;
    return count > limit ? limit : count;
}
