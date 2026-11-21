/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09895(unsigned int count)
{
    const unsigned int limit = 148u;
    return count > limit ? limit : count;
}
